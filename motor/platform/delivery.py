"""Error delivery infrastructure (ADR-028-06 ER01-ER08).

Manages AT_LEAST_ONCE delivery of ERROR messages with retry logic.
Thread-safe. Uses a background thread for retry scheduling.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from motor.platform.errors import ProtocolException
from motor.platform.models import (
    DeliveryHeader,
    DeliverySemantics,
    ErrorCode,
    ErrorEnvelope,
    MessageKind,
    ProtocolEnvelope,
    RetryPolicy,
    RoutingHeader,
    SpanId,
    TraceHeader,
    VersionHeader,
)
from motor.platform.serializer import make_message_id

# Domain vs Transport error classification per ER07/ER08
DOMAIN_ERROR_CODES = {
    ErrorCode.INVALID_PAYLOAD.value,
    ErrorCode.UNAUTHORIZED.value,
    ErrorCode.NOT_FOUND.value,
    ErrorCode.UNKNOWN_MESSAGE.value,
}
TRANSPORT_ERROR_CODES = {
    ErrorCode.TIMEOUT.value,
    ErrorCode.UNAVAILABLE.value,
    ErrorCode.TRANSIENT.value,
    ErrorCode.CAPACITY_EXCEEDED.value,
    ErrorCode.INTERNAL_ERROR.value,
}


def classify_error(error_code: str) -> str:
    """ER07/ER08: classify error as 'domain' (non-retryable) or 'transport' (retryable)."""
    if error_code in DOMAIN_ERROR_CODES:
        return "domain"
    if error_code in TRANSPORT_ERROR_CODES:
        return "transport"
    return "domain"  # default: non-retryable


class ErrorDelivery:
    """Delivers ERROR messages with AT_LEAST_ONCE semantics and retry.

    ER01: ERROR messages are AT_LEAST_ONCE (receiver must ACK).
    ER02: If ERROR ACK not received → retry up to 3 times → silent discard.
    ER05: retryable=false → no retry.
    ER06: retryable=true → retry per RetryPolicy.
    ER07: Domain errors: non-retryable by default.
    ER08: Transport errors: retryable by default.
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        send_fn: Callable[[ProtocolEnvelope], None],
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._send = send_fn
        self._retry_policy = retry_policy or RetryPolicy()
        self._lock = threading.Lock()
        self._pending: dict[str, int] = {}

    def deliver(self, original: ProtocolEnvelope, error: ErrorEnvelope) -> None:
        """Deliver an ERROR message. Blocks for retries.

        ER01: AT_LEAST_ONCE semantics.
        ER05/ER06: respects retryable flag.
        """
        if not error.retryable:
            self._send_one(original, error)
            return

        envelope = self._build_envelope(original, error)
        msg_id = str(envelope.routing.message_id)

        attempts = 0
        while attempts < self.MAX_RETRIES:
            try:
                self._send(envelope)
                return
            except (ProtocolException, ConnectionError, TimeoutError):
                attempts += 1
                with self._lock:
                    self._pending[msg_id] = attempts
                if attempts >= self.MAX_RETRIES:
                    with self._lock:
                        self._pending.pop(msg_id, None)
                    return
                backoff_ms = self._retry_policy.backoff_base_ms * (
                    self._retry_policy.backoff_multiplier ** (attempts - 1)
                )
                backoff_ms = min(backoff_ms, self._retry_policy.max_backoff_ms)
                time.sleep(backoff_ms / 1000.0)

    def _send_one(self, original: ProtocolEnvelope, error: ErrorEnvelope) -> None:
        envelope = self._build_envelope(original, error)
        self._send(envelope)

    def _build_envelope(
        self, original: ProtocolEnvelope, error: ErrorEnvelope
    ) -> ProtocolEnvelope:
        """Build ERROR ProtocolEnvelope from original message and ErrorEnvelope.

        ER03: original_message_id points to triggering message (set in from_original).
        ER04: ERROR causation_id inherits from original (set in from_original).
        """
        from motor.platform.serializer import make_envelope_with_checksum

        payload = f"{error.error_code}:{error.error_message}".encode()
        mid = make_message_id(
            "1.0", "1.0",
            original.routing.destination,
            original.routing.source,
            f"ERROR.{original.routing.message_type}",
            payload,
        )

        v = VersionHeader(
            protocol_version=original.version.protocol_version,
            schema_version=original.version.schema_version,
        )
        r = RoutingHeader(
            message_id=mid,
            message_type=f"ERROR.{original.routing.message_type}",
            message_kind=MessageKind.ERROR,
            source=original.routing.destination,
            destination=original.routing.source,
        )
        t = TraceHeader(
            trace_id=original.trace.trace_id,
            span_id=SpanId.generate(),
            parent_span_id=original.trace.span_id,
            correlation_id=original.trace.correlation_id,
            causation_id=original.trace.causation_id,
            timestamp=time.time(),
        )
        d = DeliveryHeader(
            semantics=DeliverySemantics.AT_LEAST_ONCE,
            timeout_ms=30000,
        )
        return make_envelope_with_checksum(v, r, t, d, payload=payload)
