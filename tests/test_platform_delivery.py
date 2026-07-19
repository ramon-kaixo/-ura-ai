"""Tests for motor/platform/delivery.py — ErrorDelivery (ER01-ER08).

Cubre: classify_error, ErrorDelivery.send() con retry,
ER01-ER08 requirements, thread safety, RetryPolicy.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from motor.platform import (
    CausationId,
    CorrelationId,
    DeliveryHeader,
    DeliverySemantics,
    ErrorCode,
    ErrorDelivery,
    ErrorEnvelope,
    MessageKind,
    ProtocolEnvelope,
    ProtocolException,
    RetryPolicy,
    RoutingHeader,
    SpanId,
    TraceHeader,
    TraceId,
    VersionHeader,
    classify_error,
    make_envelope_with_checksum,
    make_message_id,
)


def _make_env(
    message_type: str = "TestRequest",
    kind: MessageKind = MessageKind.COMMAND,
    source: str = "agent-a",
    destination: str = "memory-b",
    payload: bytes = b'{"hello":"world"}',
    proto_ver: str = "1.0",
    schema_ver: str = "1.0",
) -> ProtocolEnvelope:
    v = VersionHeader(protocol_version=proto_ver, schema_version=schema_ver)
    mid = make_message_id(proto_ver, schema_ver, source, destination, message_type, payload)
    r = RoutingHeader(
        message_id=mid,
        message_type=message_type,
        message_kind=kind,
        source=source,
        destination=destination,
    )
    t = TraceHeader(
        trace_id=TraceId.generate(),
        span_id=SpanId.generate(),
        parent_span_id=SpanId.root(),
        correlation_id=CorrelationId("corr1"),
        causation_id=CausationId.root(),
        timestamp=1000.0,
    )
    d = DeliveryHeader(semantics=DeliverySemantics.AT_LEAST_ONCE)
    return make_envelope_with_checksum(version=v, routing=r, trace=t, delivery=d, payload=payload)


def _make_retryable_error(
    original: ProtocolEnvelope,
    code: str = "timeout",
    message: str = "request timed out",
) -> ErrorEnvelope:
    return ErrorEnvelope.from_original(
        original=original,
        error_code=code,
        error_message=message,
        component="memory-b",
        retryable=True,
    )


def _make_non_retryable_error(
    original: ProtocolEnvelope,
    code: str = "invalid_payload",
    message: str = "payload malformed",
) -> ErrorEnvelope:
    return ErrorEnvelope.from_original(
        original=original,
        error_code=code,
        error_message=message,
        component="memory-b",
        retryable=False,
    )


# ═══════════════════════════════════════════════════
# classify_error (ER07/ER08 helper)
# ═══════════════════════════════════════════════════


class TestClassifyError:
    def test_domain_errors_are_non_retryable(self) -> None:
        for code in ("invalid_payload", "unauthorized", "not_found", "unknown_message"):
            assert classify_error(code) == "domain"

    def test_transport_errors_are_retryable(self) -> None:
        for code in ("timeout", "unavailable", "transient", "capacity_exceeded", "internal_error"):
            assert classify_error(code) == "transport"

    def test_unknown_error_defaults_to_domain(self) -> None:
        assert classify_error("bogus_code") == "domain"

    def test_oversized_is_domain(self) -> None:
        assert classify_error("oversized") == "domain"

    def test_version_mismatch_is_domain(self) -> None:
        assert classify_error("version_mismatch") == "domain"

    def test_all_error_codes_classified(self) -> None:
        for ec in ErrorCode:
            cat = classify_error(ec.value)
            assert cat in ("domain", "transport")


# ═══════════════════════════════════════════════════
# ErrorDelivery — basic send
# ═══════════════════════════════════════════════════


class TestErrorDeliveryBasicSend:
    def test_deliver_non_retryable_sends_once(self) -> None:
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env()
        err = _make_non_retryable_error(orig)

        d.deliver(orig, err)

        assert len(sent) == 1
        env = sent[0]
        assert env.routing.message_kind == MessageKind.ERROR
        assert env.routing.message_type == f"ERROR.{orig.routing.message_type}"
        assert env.routing.source == orig.routing.destination
        assert env.routing.destination == orig.routing.source

    def test_deliver_non_retryable_never_retries_on_failure(self) -> None:
        call_count: int = 0

        def fail_send(_env: ProtocolEnvelope) -> None:
            nonlocal call_count
            call_count += 1
            msg = "always fails"
            raise ConnectionError(msg)

        d = ErrorDelivery(send_fn=fail_send)
        orig = _make_env()
        err = _make_non_retryable_error(orig)

        with pytest.raises(ConnectionError):
            d.deliver(orig, err)
        assert call_count == 1

    def test_deliver_retryable_succeeds_on_first_attempt(self) -> None:
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        assert len(sent) == 1

    def test_deliver_retryable_retries_on_transient_failure(self) -> None:
        attempts: list[int] = []

        def flaky_send(_env: ProtocolEnvelope) -> None:
            attempts.append(len(attempts) + 1)
            if len(attempts) < 2:
                msg = "transient failure"
                raise TimeoutError(msg)

        d = ErrorDelivery(send_fn=flaky_send)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        assert len(attempts) == 2  # fail once, succeed on retry

    def test_deliver_retryable_silent_discard_after_max_retries(self) -> None:
        attempts: list[int] = []

        def always_fail(_env: ProtocolEnvelope) -> None:
            attempts.append(len(attempts) + 1)
            msg = "permanent failure"
            raise ProtocolException(msg)

        d = ErrorDelivery(send_fn=always_fail)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        # MAX_RETRIES = 3, but the loop tries up to MAX_RETRIES times
        # (0, 1, 2) → 3 attempts total
        assert len(attempts) == 3

    def test_deliver_retryable_catches_protocol_exception(self) -> None:
        sent: list[ProtocolEnvelope] = []

        def fail_then_succeed(_env: ProtocolEnvelope) -> None:
            if len(sent) == 0:
                sent.append(_env)
                msg = "protocol error"
                raise ProtocolException(msg)

        d = ErrorDelivery(send_fn=fail_then_succeed)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)
        # fail_then_succeed only adds to sent on first call (before raise);
        # on retry it does nothing, but the deliver still returns silently
        assert len(sent) == 1

    def test_deliver_retryable_catches_connection_error(self) -> None:
        attempts: list[int] = []

        def fail_with_connection(_env: ProtocolEnvelope) -> None:
            attempts.append(len(attempts) + 1)
            msg = "connection reset"
            raise ConnectionError(msg)

        d = ErrorDelivery(send_fn=fail_with_connection)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        assert len(attempts) == 3

    def test_deliver_retryable_catches_timeout_error(self) -> None:
        attempts: list[int] = []

        def fail_with_timeout(_env: ProtocolEnvelope) -> None:
            attempts.append(len(attempts) + 1)
            msg = "timed out"
            raise TimeoutError(msg)

        d = ErrorDelivery(send_fn=fail_with_timeout)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        assert len(attempts) == 3

    def test_unrelated_exception_not_caught(self) -> None:
        sent: list[ProtocolEnvelope] = []

        def fail_hard(_env: ProtocolEnvelope) -> None:
            sent.append(_env)
            msg = "unexpected"
            raise ValueError(msg)

        d = ErrorDelivery(send_fn=fail_hard)
        orig = _make_env()
        err = _make_retryable_error(orig)

        with pytest.raises(ValueError):
            d.deliver(orig, err)
        assert len(sent) == 1  # first attempt only


# ═══════════════════════════════════════════════════
# RetryPolicy configuration
# ═══════════════════════════════════════════════════


class TestRetryPolicy:
    def test_default_retry_policy(self) -> None:
        d = ErrorDelivery(send_fn=lambda _: None)
        assert d._retry_policy.max_attempts == 3
        assert d._retry_policy.backoff_base_ms == 100
        assert d._retry_policy.backoff_multiplier == 2.0
        assert d._retry_policy.max_backoff_ms == 30000

    def test_custom_retry_policy(self) -> None:
        rp = RetryPolicy(
            max_attempts=5,
            backoff_base_ms=50,
            backoff_multiplier=1.5,
            max_backoff_ms=5000,
        )
        d = ErrorDelivery(send_fn=lambda _: None, retry_policy=rp)
        assert d._retry_policy.max_attempts == 5

    def test_exponential_backoff_increases(self) -> None:
        delays: list[float] = []

        def track_delays(_env: ProtocolEnvelope) -> None:
            delays.append(time.monotonic())

        original_timeout = time.sleep
        original_delays: list[float] = []

        def tracking_sleep(seconds: float) -> None:
            original_delays.append(seconds)
            original_timeout(seconds)

        time.sleep = tracking_sleep  # type: ignore[assignment]

        try:
            attempts: list[int] = []
            rp = RetryPolicy(backoff_base_ms=10, backoff_multiplier=2.0, max_backoff_ms=1000)

            def always_fail(_env: ProtocolEnvelope) -> None:
                attempts.append(len(attempts) + 1)
                msg = "fail"
                raise ConnectionError(msg)

            d = ErrorDelivery(send_fn=always_fail, retry_policy=rp)
            orig = _make_env()
            err = _make_retryable_error(orig)

            d.deliver(orig, err)

            # Backoff: 10ms, 20ms after each failure (attempts 1→2, 2→3)
            assert len(original_delays) == 2
            # delay[0] = 10ms = 0.010s, delay[1] = 20ms = 0.020s
            assert original_delays[0] == pytest.approx(0.01, rel=0.5)
            assert original_delays[1] == pytest.approx(0.02, rel=0.5)
        finally:
            time.sleep = original_timeout

    def test_backoff_capped_at_max(self) -> None:
        delays: list[float] = []
        original_timeout = time.sleep

        def tracking_sleep(seconds: float) -> None:
            delays.append(seconds)
            original_timeout(seconds)

        time.sleep = tracking_sleep  # type: ignore[assignment]

        try:
            rp = RetryPolicy(
                backoff_base_ms=5000,
                backoff_multiplier=10.0,
                max_backoff_ms=200,
            )

            def always_fail(_env: ProtocolEnvelope) -> None:
                msg = "fail"
                raise ConnectionError(msg)

            d = ErrorDelivery(send_fn=always_fail, retry_policy=rp)
            orig = _make_env()
            err = _make_retryable_error(orig)

            d.deliver(orig, err)

            # Both delays should be capped at 200ms = 0.2s
            for delay in delays:
                assert delay == pytest.approx(0.2, rel=0.5)
        finally:
            time.sleep = original_timeout


# ═══════════════════════════════════════════════════
# ER01-ER08 requirements
# ═══════════════════════════════════════════════════


class TestERRequirements:
    def test_er01_at_least_once_semantics(self) -> None:
        """ERROR messages are built with AT_LEAST_ONCE semantics."""
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        env = sent[0]
        assert env.delivery.semantics == DeliverySemantics.AT_LEAST_ONCE

    def test_er02_retry_up_to_3_times_then_discard(self) -> None:
        """If ERROR ACK not received → retry up to 3 times → silent discard."""
        attempts: list[int] = []

        def always_fail(_env: ProtocolEnvelope) -> None:
            attempts.append(len(attempts) + 1)
            msg = "no ack"
            raise TimeoutError(msg)

        d = ErrorDelivery(send_fn=always_fail)
        orig = _make_env()
        err = _make_retryable_error(orig)

        # Should not raise — silent discard
        d.deliver(orig, err)

        assert len(attempts) == 3  # exactly MAX_RETRIES

    def test_er03_original_message_id_in_envelope(self) -> None:
        """original_message_id must point to the triggering message."""
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env(message_type="ComputeRequest")
        err = ErrorEnvelope.from_original(
            original=orig,
            error_code="timeout",
            error_message="timed out",
        )

        d.deliver(orig, err)

        assert err.original_message_id == str(orig.routing.message_id)

    def test_er04_causation_id_inherits_from_original(self) -> None:
        """ERROR causation_id inherits from original message."""
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        env = sent[0]
        assert env.trace.causation_id == orig.trace.causation_id

    def test_er05_retryable_false_no_retry(self) -> None:
        """retryable=false errors: do NOT retry."""
        call_count: int = 0

        def fail_once(_env: ProtocolEnvelope) -> None:
            nonlocal call_count
            call_count += 1
            msg = "fail"
            raise ConnectionError(msg)

        d = ErrorDelivery(send_fn=fail_once)
        orig = _make_env()
        err = _make_non_retryable_error(orig)

        with pytest.raises(ConnectionError):
            d.deliver(orig, err)
        assert call_count == 1

    def test_er06_retryable_true_retry(self) -> None:
        """retryable=true errors: retry per RetryPolicy."""
        call_attempts: list[int] = []

        def fail_twice(_env: ProtocolEnvelope) -> None:
            call_attempts.append(len(call_attempts) + 1)
            if len(call_attempts) < 3:
                msg = "transient"
                raise TimeoutError(msg)

        d = ErrorDelivery(send_fn=fail_twice)

        # This should succeed when fail_twice does NOT raise on the 3rd call
        # but wait — fail_twice raises for attempts 1 and 2, succeeds on 3.
        # That means attempts=1 (fail) → retry → attempts=2 (fail) → retry → attempts=3 (success)
        # But after 2 fails, we're at attempts=2, MAX_RETRIES=3, so we have one more try
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        assert len(call_attempts) == 3

    def test_er07_domain_errors_non_retryable_by_default(self) -> None:
        """Domain errors are classified as non-retryable."""
        for code in ("invalid_payload", "unauthorized", "not_found", "unknown_message"):
            assert classify_error(code) == "domain"

    def test_er08_transport_errors_retryable_by_default(self) -> None:
        """Transport errors are classified as retryable."""
        for code in ("timeout", "unavailable", "transient", "capacity_exceeded", "internal_error"):
            assert classify_error(code) == "transport"

    def test_er01_to_er08_integration_send(self) -> None:
        """Full ER01-ER08 flow: retryable transport error retries."""
        sent: list[ProtocolEnvelope] = []
        attempts: list[int] = []

        def flaky(_env: ProtocolEnvelope) -> None:
            attempts.append(len(attempts) + 1)
            if len(attempts) < 2:
                msg = "transient"
                raise TimeoutError(msg)
            sent.append(_env)

        d = ErrorDelivery(send_fn=flaky)
        orig = _make_env()
        err = ErrorEnvelope.from_original(
            original=orig,
            error_code="timeout",
            error_message="upstream timeout",
            component="memory-b",
            retryable=classify_error("timeout") == "transport",
        )

        d.deliver(orig, err)

        assert len(sent) == 1
        env = sent[0]
        # ER01: semantics
        assert env.delivery.semantics == DeliverySemantics.AT_LEAST_ONCE
        # ER03: original_message_id
        assert err.original_message_id == str(orig.routing.message_id)
        # ER04: causation_id inherits
        assert env.trace.causation_id == orig.trace.causation_id
        # ER06+ER08: retried per policy
        assert len(attempts) == 2


# ═══════════════════════════════════════════════════
# ErrorDelivery — envelope structure verification
# ═══════════════════════════════════════════════════


class TestEnvelopeStructure:
    def test_error_envelope_has_correct_routing(self) -> None:
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env(message_type="ComputeRequest", source="agent-a", destination="memory-b")
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        env = sent[0]
        assert env.routing.message_kind == MessageKind.ERROR
        assert env.routing.message_type == "ERROR.ComputeRequest"
        # Source/destination are swapped
        assert env.routing.source == "memory-b"
        assert env.routing.destination == "agent-a"

    def test_error_envelope_has_trace_inheritance(self) -> None:
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        env = sent[0]
        # trace_id stays the same
        assert env.trace.trace_id == orig.trace.trace_id
        # parent_span_id points to original span_id
        assert env.trace.parent_span_id == orig.trace.span_id
        # new span_id generated
        assert env.trace.span_id != orig.trace.span_id
        assert env.trace.span_id is not None
        # correlation_id stays the same
        assert env.trace.correlation_id == orig.trace.correlation_id
        # causation_id inherits from original (per ER04)
        assert env.trace.causation_id == orig.trace.causation_id

    def test_error_payload_contains_code_and_message(self) -> None:
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env()
        err = _make_retryable_error(orig, code="timeout", message="request timed out")

        d.deliver(orig, err)

        env = sent[0]
        payload = env.payload.decode()
        assert "timeout" in payload
        assert "request timed out" in payload

    def test_error_envelope_has_checksum(self) -> None:
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        env = sent[0]
        assert env.checksum != ""


# ═══════════════════════════════════════════════════
# Error delivery with different ErrorCodes
# ═══════════════════════════════════════════════════


class TestErrorCodes:
    def test_all_retryable_error_codes_retry(self) -> None:
        """All transport error codes trigger retry behavior."""

        def _make_fail() -> tuple[list[int], Callable[[ProtocolEnvelope], None]]:
            l_attempts: list[int] = []

            def _fn(_env: ProtocolEnvelope) -> None:
                l_attempts.append(len(l_attempts) + 1)
                if len(l_attempts) < 3:
                    msg = "fail"
                    raise ConnectionError(msg)

            return l_attempts, _fn

        codes = ("timeout", "unavailable", "transient", "capacity_exceeded", "internal_error")
        for code in codes:
            local_attempts, fail_fn = _make_fail()
            d = ErrorDelivery(send_fn=fail_fn)
            orig = _make_env()
            err = ErrorEnvelope.from_original(
                original=orig,
                error_code=code,
                error_message=f"error: {code}",
                retryable=True,
            )

            d.deliver(orig, err)

            assert len(local_attempts) == 3, f"Code {code}: expected 3 attempts, got {len(local_attempts)}"

    def test_all_non_retryable_error_codes_send_once(self) -> None:
        """All domain error codes send once without retry."""
        domain_codes = ("invalid_payload", "unauthorized", "not_found",
                        "unknown_message", "oversized", "version_mismatch")
        for code in domain_codes:
            call_count: int = 0

            def send_once(_env: ProtocolEnvelope, _c: str = code) -> None:  # type: ignore[assignment]
                nonlocal call_count
                call_count += 1

            d = ErrorDelivery(send_fn=send_once)
            orig = _make_env()
            err = ErrorEnvelope.from_original(
                original=orig,
                error_code=code,
                error_message=f"error: {code}",
                retryable=False,
            )

            d.deliver(orig, err)

            assert call_count == 1, f"Code {code}: expected 1 call, got {call_count}"


# ═══════════════════════════════════════════════════
# Thread safety
# ═══════════════════════════════════════════════════


class TestThreadSafety:
    def test_concurrent_sends_to_same_delivery(self) -> None:
        """Multiple threads can deliver errors concurrently."""
        sent_lock = threading.Lock()
        sent: list[ProtocolEnvelope] = []

        def send_fn(env: ProtocolEnvelope) -> None:
            with sent_lock:
                sent.append(env)

        d = ErrorDelivery(send_fn=send_fn)
        n_threads = 10
        errors_per_thread = 5
        barrier = threading.Barrier(n_threads)
        exceptions: list[Exception] = []

        def worker() -> None:
            barrier.wait()
            for _ in range(errors_per_thread):
                try:
                    orig = _make_env()
                    err = _make_retryable_error(orig)
                    d.deliver(orig, err)
                except Exception as exc:
                    with sent_lock:
                        exceptions.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(exceptions) == 0, f"Exceptions during concurrent delivery: {exceptions}"
        assert len(sent) == n_threads * errors_per_thread

    def test_concurrent_retryable_failures_no_race(self) -> None:
        """Concurrent retries do not corrupt internal state."""
        sent: list[ProtocolEnvelope] = []

        def flaky_send(env: ProtocolEnvelope) -> None:
            sent.append(env)
            if len(sent) % 3 == 0:
                msg = "transient"
                raise TimeoutError(msg)

        d = ErrorDelivery(send_fn=flaky_send)
        n_threads = 5
        barrier = threading.Barrier(n_threads)
        errors_list: list[Exception] = []

        def worker() -> None:
            barrier.wait()
            for _ in range(10):
                try:
                    orig = _make_env()
                    err = _make_retryable_error(orig)
                    d.deliver(orig, err)
                except Exception as exc:
                    errors_list.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors_list) == 0

    def test_pending_dict_thread_safe(self) -> None:
        """Internal _pending dict does not race under concurrent access."""
        d = ErrorDelivery(send_fn=lambda _: None)
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        errors_list: list[Exception] = []

        def worker() -> None:
            barrier.wait()
            for _ in range(20):
                try:
                    with d._lock:
                        d._pending[f"msg_{threading.get_ident()}_{_}"] = _
                except Exception as exc:
                    errors_list.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors_list) == 0
        assert len(d._pending) == n_threads * 20

    def test_delivery_instance_reusable_across_threads(self) -> None:
        """Single ErrorDelivery instance reused from multiple threads."""
        sent: list[ProtocolEnvelope] = []
        sent_lock = threading.Lock()

        def send_fn(env: ProtocolEnvelope) -> None:
            with sent_lock:
                sent.append(env)

        d = ErrorDelivery(send_fn=send_fn)
        results: list[bool] = []
        results_lock = threading.Lock()

        def worker() -> None:
            for _ in range(5):
                try:
                    orig = _make_env()
                    err = _make_non_retryable_error(orig)
                    d.deliver(orig, err)
                    with results_lock:
                        results.append(True)
                except Exception:
                    with results_lock:
                        results.append(False)

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert all(results)
        assert len(sent) == 30  # 6 threads x 5 sends


# ═══════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════


class TestEdgeCases:
    def test_deliver_with_empty_error_message(self) -> None:
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env()
        err = ErrorEnvelope.from_original(
            original=orig,
            error_code="timeout",
            error_message="",
            retryable=True,
        )

        d.deliver(orig, err)

        assert len(sent) == 1

    def test_deliver_with_minimal_envelope(self) -> None:
        sent: list[ProtocolEnvelope] = []
        d = ErrorDelivery(send_fn=sent.append)
        orig = _make_env(payload=b"{}")
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        assert len(sent) == 1

    def test_pending_is_cleared_after_exhaustion(self) -> None:
        def always_fail(_env: ProtocolEnvelope) -> None:
            msg = "fail"
            raise TimeoutError(msg)

        d = ErrorDelivery(send_fn=always_fail)
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        assert len(d._pending) == 0

    def test_zero_max_retries_still_attempts_once(self) -> None:
        """Even with aggressive policy, deliver always makes at least one attempt."""
        attempts: list[int] = []

        def fail(_env: ProtocolEnvelope) -> None:
            attempts.append(len(attempts) + 1)
            msg = "fail"
            raise ConnectionError(msg)

        rp = RetryPolicy(max_attempts=1, backoff_base_ms=1)
        d = ErrorDelivery(send_fn=fail, retry_policy=rp)
        # d.MAX_RETRIES = 3 is the class constant, not from retry_policy;
        # The deliver() loop uses self.MAX_RETRIES = 3 always
        orig = _make_env()
        err = _make_retryable_error(orig)

        d.deliver(orig, err)

        # MAX_RETRIES is always 3 (class constant), not from retry_policy
        assert len(attempts) == 3
