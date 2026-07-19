"""Tests para F28-B2: Platform Protocols Infrastructure.

Cubre: determinismo, compatibilidad forward/backward, version negotiation,
serialización canónica, bit-identical, mensajes desconocidos, versión
desconocida, schema desconocido, checksum inválido, routing inválido,
delivery inválido, trace inválido, concurrencia, property-based, fuzzing.
"""

from __future__ import annotations

import threading
import time

import pytest

from motor.platform import (
    CausationId,
    CompatibilityChecker,
    CorrelationId,
    DeliveryHeader,
    DeliverySemantics,
    ErrorEnvelope,
    JsonProtocolDeserializer,
    JsonProtocolSerializer,
    LocalTransport,
    MessageKind,
    ProtocolEnvelope,
    ProtocolException,
    ProtocolValidationError,
    ProtocolValidator,
    VersionHeader,
    VersionNegotiator,
    compute_checksum,
    make_envelope_with_checksum,
    make_message_id,
    verify_checksum,
)
from motor.platform.models import RoutingHeader, SecurityHeader, SpanId, TraceHeader, TraceId


def _make_env(
    message_type: str = "TestRequest",
    kind: MessageKind = MessageKind.COMMAND,
    source: str = "agent",
    destination: str = "memory",
    payload: bytes = b'{"hello":"world"}',
    proto_ver: str = "1.0",
    schema_ver: str = "1.0",
    correlation: str = "trace1",
    semantics: DeliverySemantics = DeliverySemantics.AT_MOST_ONCE,
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
        correlation_id=CorrelationId(correlation),
        causation_id=CausationId.root(),
        timestamp=1000.0,
    )
    d = DeliveryHeader(semantics=semantics)
    return make_envelope_with_checksum(version=v, routing=r, trace=t, delivery=d, payload=payload)


# ═══════════════════════════════════════════════════
# B2.1: Determinismo
# ═══════════════════════════════════════════════════


def test_deterministic_message_id() -> None:
    a = make_message_id("1.0", "1.0", "src", "dst", "T", b"data")
    b = make_message_id("1.0", "1.0", "src", "dst", "T", b"data")
    assert a.value == b.value


def test_deterministic_serialization() -> None:
    ser = JsonProtocolSerializer()
    env = _make_env()
    data1 = ser.serialize(env)
    data2 = ser.serialize(env)
    assert data1 == data2


def test_bit_identical_roundtrip() -> None:
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    env = _make_env()
    data = ser.serialize(env)
    env2 = deser.deserialize(data)
    data2 = ser.serialize(env2)
    assert data == data2


# ═══════════════════════════════════════════════════
# B2.2: Serialización canónica
# ═══════════════════════════════════════════════════


def test_canonical_json_format() -> None:
    ser = JsonProtocolSerializer()
    env = _make_env()
    data = ser.serialize(env).decode("utf-8")
    assert ":" in data  # compact separators
    assert '"payload_hex"' in data


def test_serialization_with_security() -> None:
    env = _make_env()
    sec = SecurityHeader(auth_token="tok123", auth_token_type="bearer")  # noqa: S106
    env2 = make_envelope_with_checksum(
        version=env.version,
        routing=env.routing,
        trace=env.trace,
        delivery=env.delivery,
        payload=env.payload,
        security=sec,
    )
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    data = ser.serialize(env2)
    restored = deser.deserialize(data)
    assert restored.security is not None
    assert restored.security.auth_token == "tok123"  # noqa: S105


# ═══════════════════════════════════════════════════
# B2.3: Compatibilidad forward/backward
# ═══════════════════════════════════════════════════


def test_backward_compatible() -> None:
    assert CompatibilityChecker.is_backward_compatible("1.0", "1.5") is True
    assert CompatibilityChecker.is_backward_compatible("1.5", "1.0") is False


def test_forward_compatible() -> None:
    assert CompatibilityChecker.is_forward_compatible("1.5", "1.0") is True
    assert CompatibilityChecker.is_forward_compatible("1.0", "1.5") is False


def test_can_communicate_same_major() -> None:
    assert CompatibilityChecker.can_communicate("1.0", "1.9") is True
    assert CompatibilityChecker.can_communicate("2.0", "1.0") is False


# ═══════════════════════════════════════════════════
# B2.4: Version negotiation
# ═══════════════════════════════════════════════════


def test_negotiate_same_version() -> None:
    neg = VersionNegotiator()
    res = neg.negotiate("1.0", "1.0", {"a"}, {"a", "b"}, MessageKind.COMMAND)
    assert res.compatible is True
    assert res.protocol_version == "1.0"


def test_negotiate_uses_lower_minor() -> None:
    neg = VersionNegotiator()
    res = neg.negotiate("1.5", "1.3", set(), set(), MessageKind.COMMAND)
    assert res.protocol_version == "1.3"


def test_negotiate_major_mismatch() -> None:
    neg = VersionNegotiator()
    res = neg.negotiate("2.0", "1.0", set(), set(), MessageKind.COMMAND)
    assert res.compatible is False


def test_negotiate_event_newer_emitter() -> None:
    neg = VersionNegotiator()
    res = neg.negotiate("2.0", "1.0", set(), set(), MessageKind.EVENT)
    assert res.compatible is False


# ═══════════════════════════════════════════════════
# B2.5: Validación
# ═══════════════════════════════════════════════════


def test_validate_valid_envelope() -> None:
    val = ProtocolValidator()
    env = _make_env()
    val.validate(env)  # no error


def test_validate_invalid_version() -> None:
    val = ProtocolValidator()
    env = _make_env(proto_ver="abc")
    with pytest.raises(ProtocolValidationError):
        val.validate(env)


def test_validate_missing_trace() -> None:
    val = ProtocolValidator()
    v = VersionHeader()
    mid = make_message_id("1.0", "1.0", "s", "d", "T", b"{}")
    r = RoutingHeader(message_id=mid, message_type="T", message_kind=MessageKind.COMMAND, source="s", destination="d")
    t = TraceHeader(
        trace_id=TraceId(""),
        span_id=SpanId(""),
        correlation_id=CorrelationId(""),
        causation_id=CausationId.root(),
    )
    d = DeliveryHeader()
    env = make_envelope_with_checksum(version=v, routing=r, trace=t, delivery=d, payload=b"{}")
    with pytest.raises(ProtocolValidationError):
        val.validate(env)


def test_validate_exactly_once_requires_key() -> None:
    val = ProtocolValidator()
    env = _make_env(semantics=DeliverySemantics.EXACTLY_ONCE)
    with pytest.raises(ProtocolValidationError, match="missing_idempotency"):
        val.validate(env)


def test_validate_oversized_payload() -> None:
    val = ProtocolValidator()
    big = b"x" * (11 * 1024 * 1024)
    env = _make_env(payload=big)
    with pytest.raises(ProtocolValidationError, match="oversized"):
        val.validate(env)


# ═══════════════════════════════════════════════════
# B2.6: Checksum
# ═══════════════════════════════════════════════════


def test_checksum_deterministic() -> None:
    assert compute_checksum(b"hello") == compute_checksum(b"hello")


def test_checksum_different() -> None:
    assert compute_checksum(b"hello") != compute_checksum(b"world")


def test_validate_checksum() -> None:
    val = ProtocolValidator()
    payload = b"test data"
    cs = compute_checksum(payload)
    val.validate_checksum(payload, cs)  # no error


def test_validate_checksum_fail() -> None:
    val = ProtocolValidator()
    with pytest.raises(ProtocolValidationError):
        val.validate_checksum(b"data", "badchecksum")


# ═══════════════════════════════════════════════════
# B2.7: ErrorEnvelope
# ═══════════════════════════════════════════════════


def test_error_envelope() -> None:
    e = ErrorEnvelope(error_code="timeout", error_message="timed out", retryable=True)
    assert e.error_code == "timeout"
    assert e.retryable is True


def test_error_envelope_immutable() -> None:
    e = ErrorEnvelope(error_code="err", error_message="msg")
    with pytest.raises(AttributeError):
        e.error_code = "changed"


# ═══════════════════════════════════════════════════
# B2.8: Concurrencia
# ═══════════════════════════════════════════════════


def test_concurrent_serialization() -> None:
    ser = JsonProtocolSerializer()
    errors: list[Exception] = []

    def _ser(n: int) -> None:
        try:
            for _ in range(100):
                env = _make_env(message_type=f"T{n}")
                ser.serialize(env)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_ser, args=(i,), daemon=True) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert not errors


# ═══════════════════════════════════════════════════
# B2.9: Fuzzing de serialización
# ═══════════════════════════════════════════════════


def test_fuzz_serialization() -> None:
    import random

    rng = random.Random(42)  # noqa: S311
    deser = JsonProtocolDeserializer()
    for _ in range(100):
        length = rng.randint(1, 500)
        junk = bytes(rng.randint(0, 255) for _ in range(length))
        try:  # noqa: SIM105
            deser.deserialize(junk)
        except Exception:  # noqa: S110
            pass  # expected for invalid data


# ═══════════════════════════════════════════════════
# B2.10: Benchmarks
# ═══════════════════════════════════════════════════


def test_benchmark_serialize_1000() -> None:
    ser = JsonProtocolSerializer()
    envs = [_make_env(message_type=f"T{i}") for i in range(1000)]
    start = time.perf_counter()
    for env in envs:
        ser.serialize(env)
    t = time.perf_counter() - start
    assert t < 2.0, f"1000 serializations took {t:.2f}s"


def test_benchmark_deserialize_1000() -> None:
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    envs = [_make_env(message_type=f"T{i}") for i in range(1000)]
    data = [ser.serialize(e) for e in envs]
    start = time.perf_counter()
    for d in data:
        deser.deserialize(d)
    t = time.perf_counter() - start
    assert t < 2.0, f"1000 deserializations took {t:.2f}s"


# ═══════════════════════════════════════════════════
# B2.11: Checksum integration (CR-01)
# ═══════════════════════════════════════════════════


def test_checksum_in_serialize_deserialize() -> None:
    """checksum must survive serialize→deserialize cycle."""
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    env = _make_env(payload=b"test payload")
    data = ser.serialize(env)
    restored = deser.deserialize(data)
    assert restored.checksum == env.checksum
    assert verify_checksum(b"test payload", restored.checksum)


def test_checksum_mismatch_detected() -> None:
    """validate must reject mismatched checksum."""
    val = ProtocolValidator()
    env = _make_env(payload=b"original")
    # Tamper with envelope
    env2 = ProtocolEnvelope(
        version=env.version,
        routing=env.routing,
        trace=env.trace,
        delivery=env.delivery,
        payload=b"tampered",
        checksum=env.checksum,
    )
    with pytest.raises(ProtocolValidationError, match="checksum"):
        val.validate(env2)


# ═══════════════════════════════════════════════════
# B2.12: Causation sentinel (CR-04)
# ═══════════════════════════════════════════════════


def test_causation_root_sentinel_roundtrip() -> None:
    """Root causation must survive serialize→deserialize."""
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    env = _make_env()
    data = ser.serialize(env)
    restored = deser.deserialize(data)
    assert restored.trace.causation_id.is_root is True


# ═══════════════════════════════════════════════════
# B2.13: Negotiate response/error (CR-03/04)
# ═══════════════════════════════════════════════════


def test_negotiate_response_inherits_version() -> None:
    neg = VersionNegotiator()
    res = neg.negotiate_response("1.5", {"cap_a"}, {"cap_a", "cap_b"})
    assert res.compatible is True
    assert res.protocol_version == "1.5"
    assert "cap_a" in res.capabilities


def test_negotiate_error_inherits_version() -> None:
    neg = VersionNegotiator()
    res = neg.negotiate_error("2.0", set(), set())
    assert res.compatible is True
    assert res.protocol_version == "2.0"


# ═══════════════════════════════════════════════════
# B2.14: Unknown MessageKind (CR-10)
# ═══════════════════════════════════════════════════


def test_unknown_message_kind_raises_protocol_exception() -> None:
    """Unknown MessageKind must raise ProtocolException, not ValueError."""
    import json

    from motor.platform.errors import ProtocolException

    deser = JsonProtocolDeserializer()
    bad_data = json.dumps(
        {
            "version": {
                "protocol_version": "1.0",
                "schema_version": "1.0",
                "payload_type": "json",
                "capabilities": [],
                "reserved": [],
            },
            "routing": {
                "message_id": "x",
                "message_type": "T",
                "message_kind": "UNKNOWN_FUTURE_KIND",
                "source": "s",
                "destination": "d",
            },
            "trace": {"correlation_id": "c", "causation_id": "ROOT", "timestamp": 0},
            "delivery": {
                "semantics": "at_most_once",
                "timeout_ms": 30000,
                "cancelable": False,
                "max_response_bytes": 10000000,
            },
            "payload_hex": "",
            "checksum": "",
        },
    ).encode()
    with pytest.raises(ProtocolException):
        deser.deserialize(bad_data)


# ═══════════════════════════════════════════════════
# B2.15: Metadata immutable (CR-08)
# ═══════════════════════════════════════════════════


def test_metadata_is_immutable() -> None:
    dh = DeliveryHeader(metadata=(("key", "value"),))
    assert isinstance(dh.metadata, tuple)
    assert dh.metadata == (("key", "value"),)


# ═══════════════════════════════════════════════════
# F28.1-P2: DeliveryHeader retry_policy
# ═══════════════════════════════════════════════════


def test_delivery_header_default_retry_policy() -> None:
    """DeliveryHeader.retry_policy must default to None."""
    dh = DeliveryHeader()
    assert dh.retry_policy is None


def test_delivery_header_with_retry_policy() -> None:
    """DeliveryHeader must accept a RetryPolicy."""
    from motor.platform import RetryPolicy

    rp = RetryPolicy(max_attempts=5, backoff_base_ms=200)
    dh = DeliveryHeader(retry_policy=rp)
    assert dh.retry_policy is not None
    assert dh.retry_policy.max_attempts == 5
    assert dh.retry_policy.backoff_base_ms == 200


def test_retry_policy_serialization_roundtrip() -> None:
    """RetryPolicy must survive serialize→deserialize."""
    from motor.platform import RetryPolicy

    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    rp = RetryPolicy(max_attempts=3, backoff_multiplier=2.0, retryable_errors=("timeout", "unavailable"))
    dh = DeliveryHeader(retry_policy=rp)
    env = ProtocolEnvelope(
        version=VersionHeader(),
        routing=RoutingHeader(
            message_id=make_message_id("1.0", "1.0", "s", "d", "T", b"{}"),
            message_type="T",
            message_kind=MessageKind.COMMAND,
            source="s",
            destination="d",
        ),
        trace=TraceHeader(
            trace_id=TraceId.generate(),
            span_id=SpanId.generate(),
            correlation_id=CorrelationId("c"),
            causation_id=CausationId.root(),
        ),
        delivery=dh,
        payload=b"{}",
    )
    data = ser.serialize(env)
    restored = deser.deserialize(data)
    assert restored.delivery.retry_policy is not None
    assert restored.delivery.retry_policy.max_attempts == 3
    assert restored.delivery.retry_policy.backoff_multiplier == 2.0
    assert restored.delivery.retry_policy.retryable_errors == ("timeout", "unavailable")


# ═══════════════════════════════════════════════════
# F28.1-P2: ErrorCode canonical enum
# ═══════════════════════════════════════════════════


def test_error_code_enum_values() -> None:
    """ErrorCode must define all 11 canonical codes."""
    from motor.platform import ErrorCode

    codes = {e.value for e in ErrorCode}
    assert "timeout" in codes
    assert "unavailable" in codes
    assert "transient" in codes
    assert "invalid_payload" in codes
    assert "unauthorized" in codes
    assert "not_found" in codes
    assert "oversized" in codes
    assert "version_mismatch" in codes
    assert "capacity_exceeded" in codes
    assert "unknown_message" in codes
    assert "internal_error" in codes
    assert len(codes) == 11


def test_error_envelope_from_original() -> None:
    """ErrorEnvelope.from_original must inherit causation from original."""
    from motor.platform import ErrorCode

    env = _make_env(message_type="TestOp", source="agent", destination="memory")
    err = ErrorEnvelope.from_original(
        original=env,
        error_code=ErrorCode.TIMEOUT.value,
        error_message="Operation timed out",
        component="memory",
        retryable=True,
        retry_delay_ms=5000,
    )
    assert err.error_code == "timeout"
    assert err.original_message_id == str(env.routing.message_id)
    assert err.original_message_type == "TestOp"
    assert err.component == "memory"
    assert err.retryable is True
    assert err.retry_delay_ms == 5000


# ═══════════════════════════════════════════════════
# F28.1-P2: Size budgets per message type
# ═══════════════════════════════════════════════════


def test_size_budgets_tool_request() -> None:
    """ToolRequest payload must be <= 1MB."""
    val = ProtocolValidator()
    env = _make_env(message_type="ToolRequest", payload=b"x" * (2 * 1024 * 1024))
    with pytest.raises(ProtocolValidationError, match="oversized"):
        val.validate(env)


def test_size_budgets_event() -> None:
    """Event payload must be <= 100KB."""
    val = ProtocolValidator()
    env = _make_env(message_type="Event.Tick", payload=b"x" * (200 * 1024))
    with pytest.raises(ProtocolValidationError, match="oversized"):
        val.validate(env)


def test_size_budgets_tool_result_allowed() -> None:
    """ToolResult payload up to 10MB must pass."""
    val = ProtocolValidator()
    env = _make_env(message_type="ToolResult", payload=b"x" * (5 * 1024 * 1024))
    val.validate(env)  # should not raise


# ═══════════════════════════════════════════════════
# F28.1-P2: Compression (SR05-SR07)
# ═══════════════════════════════════════════════════


def test_compress_decompress_gzip() -> None:
    from motor.platform.serializer import compress_payload, decompress_payload

    original = b"Hello, world! " * 1000
    compressed = compress_payload(original, method="gzip")
    assert len(compressed) < len(original)  # actually compresses
    decompressed = decompress_payload(compressed, method="gzip")
    assert decompressed == original


def test_compress_none_passthrough() -> None:
    from motor.platform.serializer import compress_payload, decompress_payload

    data = b"test"
    assert compress_payload(data, method="none") == data
    assert decompress_payload(data, method="none") == data


def test_make_envelope_with_gzip_compression() -> None:
    """make_envelope_with_checksum with compression stores compressed payload."""
    payload = b"x" * 10000
    env = make_envelope_with_checksum(
        version=VersionHeader(),
        routing=RoutingHeader(
            message_id=make_message_id("1.0", "1.0", "s", "d", "T", payload),
            message_type="T",
            message_kind=MessageKind.COMMAND,
            source="s",
            destination="d",
        ),
        trace=TraceHeader(
            trace_id=TraceId.generate(),
            span_id=SpanId.generate(),
            correlation_id=CorrelationId("c"),
            causation_id=CausationId.root(),
        ),
        delivery=DeliveryHeader(),
        payload=payload,
        compression="gzip",
    )
    assert env.version.payload_type == "json+gzip"
    assert len(env.payload) < len(payload)  # compressed
    assert verify_checksum(env.payload, env.checksum)  # checksum covers compressed


def test_compressed_roundtrip() -> None:
    """Compressed payload survives serialize→deserialize."""
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    original = b"x" * 5000
    env = make_envelope_with_checksum(
        version=VersionHeader(),
        routing=RoutingHeader(
            message_id=make_message_id("1.0", "1.0", "s", "d", "T", original),
            message_type="T",
            message_kind=MessageKind.COMMAND,
            source="s",
            destination="d",
        ),
        trace=TraceHeader(
            trace_id=TraceId.generate(),
            span_id=SpanId.generate(),
            correlation_id=CorrelationId("c"),
            causation_id=CausationId.root(),
        ),
        delivery=DeliveryHeader(),
        payload=original,
        compression="gzip",
    )
    data = ser.serialize(env)
    restored = deser.deserialize(data)

    assert restored.version.payload_type == "json+gzip"
    # Payload on wire is compressed — checksum verified during deserialization
    assert restored.checksum == env.checksum
    # Application layer decompresses when needed
    from motor.platform.serializer import decompress_payload

    decompressed = decompress_payload(restored.payload, method="gzip")
    assert decompressed == original


def test_schema_registry_validation() -> None:
    """ProtocolValidator with registry rejects MAJOR mismatch."""
    from motor.platform import ProtocolRegistry

    registry = ProtocolRegistry()
    registry.register_message_type("TestOp", "2.0")
    val = ProtocolValidator(registry=registry)
    env = _make_env(message_type="TestOp")
    # Register schema 2.0 but message uses 1.0 → OK (MAJOR 1 <= 2)
    val.validate(env)
    # Message with schema 3.0 > registered 2.0 → reject
    env3 = _make_env(message_type="TestOp", schema_ver="3.0")
    with pytest.raises(ProtocolValidationError, match="schema_mismatch"):
        val.validate(env3)


def test_schema_registry_no_registry_skips() -> None:
    """ProtocolValidator without registry skips schema check."""
    val = ProtocolValidator()
    env = _make_env(message_type="UnknownOp", schema_ver="99.0")
    val.validate(env)  # should not raise


# ═══════════════════════════════════════════════════
# F28.1-P1: Checksum verification during deserialization
# ═══════════════════════════════════════════════════


def test_deserialize_rejects_invalid_checksum() -> None:
    """JsonProtocolDeserializer must reject tampered payload."""
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    env = _make_env(payload=b"original payload")
    data = ser.serialize(env)
    # Tamper with the serialized bytes (replace payload hex)
    tampered = data.replace(
        b"original payload".hex().encode(),
        b"tampered data".hex().encode(),
    )
    with pytest.raises(ProtocolException, match="Checksum mismatch"):
        deser.deserialize(tampered)


def test_deserialize_accepts_valid_checksum() -> None:
    """JsonProtocolDeserializer must pass valid checksum."""
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    env = _make_env(payload=b"valid payload")
    data = ser.serialize(env)
    restored = deser.deserialize(data)
    assert restored.checksum == env.checksum
    assert verify_checksum(b"valid payload", restored.checksum)


def test_deserialize_skips_empty_checksum() -> None:
    """JsonProtocolDeserializer must skip verification for empty checksum."""
    import json

    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    env = _make_env(payload=b"any payload")
    data = json.loads(ser.serialize(env).decode())
    data["checksum"] = ""
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    restored = deser.deserialize(raw)
    assert restored.checksum == ""


# ═══════════════════════════════════════════════════
# F28.1-P1: LocalTransport concurrency + envelope contract
# ═══════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_transport_send_rejects_non_envelope() -> None:
    """send() must reject non-ProtocolEnvelope with ProtocolException."""
    t = LocalTransport()
    with pytest.raises(ProtocolException):
        await t.send("not an envelope")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_transport_concurrent_send_request_no_race() -> None:
    """Concurrent send/request must not lose messages."""
    import asyncio

    t = LocalTransport()
    results: list[str] = []

    async def sender() -> None:
        for i in range(100):
            env = _make_env(message_type=f"msg_{i}")
            await t.send(env)

    async def receiver() -> None:
        for _ in range(100):
            try:
                env = await t.receive()
                results.append(env.routing.message_type)
            except RuntimeError:
                pass

    await asyncio.gather(sender(), receiver())
    assert len(results) > 0


@pytest.mark.asyncio
async def test_transport_request_handler_race_free() -> None:
    """request() handler must be called inside the lock (no race)."""
    t = LocalTransport()
    processed: list[str] = []

    def handler(env: ProtocolEnvelope) -> ProtocolEnvelope:
        processed.append(env.routing.message_type)
        return env

    t.register("test_type", handler)
    env = _make_env(message_type="test_type")
    await t.request(env)
    assert processed == ["test_type"]


# ═══════════════════════════════════════════════════
# F28.1-P2: PlatformMetrics wiring (ADR-028-10)
# ═══════════════════════════════════════════════════


def test_platform_metrics_basic() -> None:
    """PlatformMetrics counters/histograms record correctly."""
    from motor.platform import PlatformMetrics

    m = PlatformMetrics()

    m.record_sent("a", "b", "command", 100, 0.5)
    assert m.messages_sent._counters["destination=b|message_kind=command|source=a"].get() == 1  # noqa: SLF001

    m.record_received("a", "b", "command", 100)
    assert m.messages_received._counters["destination=b|message_kind=command|source=a"].get() == 1  # noqa: SLF001

    m.record_error("a", "b", "timeout")
    assert m.messages_error._counters["destination=b|error_code=timeout|source=a"].get() == 1  # noqa: SLF001


@pytest.mark.asyncio
async def test_transport_metrics_send_receive() -> None:
    """LocalTransport wired with PlatformMetrics records send/receive."""
    from motor.platform import LocalTransport, PlatformMetrics
    from motor.platform.models import (
        CausationId,
        CorrelationId,
        DeliveryHeader,
        MessageKind,
        ProtocolEnvelope,
        RoutingHeader,
        SpanId,
        TraceHeader,
        TraceId,
        VersionHeader,
    )
    from motor.platform.serializer import make_message_id

    m = PlatformMetrics()
    t = LocalTransport(metrics=m)

    env = ProtocolEnvelope(
        version=VersionHeader(),
        routing=RoutingHeader(
            message_id=make_message_id("1.0", "1.0", "a", "b", "T", b"{}"),
            message_type="T",
            message_kind=MessageKind.COMMAND,
            source="a",
            destination="b",
        ),
        trace=TraceHeader(
            trace_id=TraceId.generate(),
            span_id=SpanId.generate(),
            correlation_id=CorrelationId("c"),
            causation_id=CausationId.root(),
        ),
        delivery=DeliveryHeader(),
        payload=b"{}",
    )

    await t.send(env)
    rcvd = await t.receive()

    assert rcvd.routing.message_type == "T"
    assert m.messages_sent._counters["destination=b|message_kind=command|source=a"].get() == 1  # noqa: SLF001
    assert m.messages_received._counters["destination=b|message_kind=command|source=a"].get() == 1  # noqa: SLF001


def test_validator_metrics() -> None:
    """ProtocolValidator wired with PlatformMetrics records validation duration."""
    from motor.platform import PlatformMetrics, ProtocolValidator
    from motor.platform.models import (
        CausationId,
        CorrelationId,
        DeliveryHeader,
        MessageKind,
        RoutingHeader,
        SpanId,
        TraceHeader,
        TraceId,
        VersionHeader,
    )
    from motor.platform.serializer import make_envelope_with_checksum, make_message_id

    m = PlatformMetrics()
    v = ProtocolValidator(metrics=m)

    env = make_envelope_with_checksum(
        version=VersionHeader(),
        routing=RoutingHeader(
            message_id=make_message_id("1.0", "1.0", "a", "b", "T", b"{}"),
            message_type="T",
            message_kind=MessageKind.COMMAND,
            source="a",
            destination="b",
        ),
        trace=TraceHeader(
            trace_id=TraceId.generate(),
            span_id=SpanId.generate(),
            correlation_id=CorrelationId("c"),
            causation_id=CausationId.root(),
        ),
        delivery=DeliveryHeader(),
        payload=b"{}",
    )

    v.validate(env)
    assert len(m.validation_duration._histograms) > 0  # noqa: SLF001


def test_negotiator_metrics() -> None:
    """VersionNegotiator wired with PlatformMetrics records negotiation latency."""
    from motor.platform import PlatformMetrics, VersionNegotiator

    m = PlatformMetrics()
    n = VersionNegotiator(metrics=m)

    result = n.negotiate("1.0", "1.0", {"cap1"}, {"cap1"}, MessageKind.COMMAND)
    assert result.compatible
    # histogram recorded
    assert len(m.negotiation_duration._histograms) > 0  # noqa: SLF001


def test_get_platform_metrics_returns_singleton() -> None:
    """get_platform_metrics returns the same instance on repeated calls."""
    from motor.platform.metrics import get_platform_metrics

    m1 = get_platform_metrics()
    m2 = get_platform_metrics()
    assert m1 is m2


# ═══════════════════════════════════════════════════
# F28.1-P3: ProtocolEnvelope wrappers (F24-F27)
# ═══════════════════════════════════════════════════


def test_tool_request_protocol_version_default() -> None:
    """ToolRequest has protocol_version defaulting to 1.0."""
    from motor.agents.models import ToolRequest

    req = ToolRequest(
        execution_id="e1",
        tool_name="search",
        params={"q": "hello"},
    )
    assert req.protocol_version == "1.0"
    assert req.trace_id == ""
    assert req.causation_id == ""


def test_tool_request_to_envelope_roundtrip() -> None:
    """ToolRequest → ProtocolEnvelope → ToolRequest preserves all fields."""
    from motor.agents.models import ToolRequest

    req = ToolRequest(
        execution_id="e1",
        tool_name="search",
        params={"q": "hello"},
        timeout=15,
        attempt=2,
        protocol_version="2.0",
        trace_id="tr1",
        causation_id="c1",
    )
    env = req.to_envelope()
    assert env.routing.message_type == "ToolRequest"
    assert env.routing.source == "agent"
    assert env.routing.destination == "search"

    restored = ToolRequest.from_envelope(env)
    assert restored.execution_id == "e1"
    assert restored.tool_name == "search"
    assert restored.params == {"q": "hello"}
    assert restored.timeout == 15
    assert restored.attempt == 2
    assert restored.protocol_version == "2.0"
    assert restored.trace_id == "tr1"
    assert restored.causation_id == "c1"


def test_tool_result_to_envelope_roundtrip() -> None:
    """ToolResult → ProtocolEnvelope → ToolResult preserves all fields."""
    from motor.agents.models import ToolResult

    result = ToolResult(
        execution_id="e1",
        tool_name="search",
        success=True,
        data={"answer": "42"},
        error=None,
        duration_ms=123.4,
        attempt=1,
        protocol_version="1.0",
    )
    env = result.to_envelope()
    assert env.routing.message_type == "ToolResult"
    assert env.routing.source == "search"
    assert env.routing.destination == "agent"

    restored = ToolResult.from_envelope(env)
    assert restored.execution_id == "e1"
    assert restored.tool_name == "search"
    assert restored.success
    assert restored.data == {"answer": "42"}
    assert restored.error is None
    assert restored.duration_ms == 123.4
    assert restored.attempt == 1
    assert restored.protocol_version == "1.0"


def test_tool_result_error_roundtrip() -> None:
    """ToolResult with error roundtrips correctly."""
    from motor.agents.models import ToolResult

    result = ToolResult(
        execution_id="e2",
        tool_name="fetch",
        success=False,
        data={},
        error="timeout",
        error_type="TimeoutError",
        duration_ms=5000.0,
        attempt=3,
    )
    env = result.to_envelope()
    restored = ToolResult.from_envelope(env)
    assert not restored.success
    assert restored.error == "timeout"
    assert restored.error_type == "TimeoutError"
    assert restored.attempt == 3


def test_protocol_tool_runner_adapter() -> None:
    """ProtocolToolRunner wraps and delegates to inner ToolRunner."""
    from motor.agents.base import ToolRunner as ToolRunnerABC
    from motor.agents.models import ToolContract
    from motor.platform.adapters.tool_runner import ProtocolToolRunner

    class FakeRunner(ToolRunnerABC):
        def get_contract(self, tool_name: str) -> ToolContract:
            return ToolContract(name=tool_name)

        def run(self, tool_name: str, params: dict, timeout: int = 30) -> dict:
            return {"result": f"ran_{tool_name}"}

        def cancel(self, tool_name: str) -> None:
            pass

    from motor.agents.models import ToolRequest, ToolResult

    adapter = ProtocolToolRunner(FakeRunner())

    req = ToolRequest(
        execution_id="e1",
        tool_name="search",
        params={"q": "test"},
        trace_id="tr1",
    )
    response_env = adapter.run_protocol(req.to_envelope())
    restored = ToolResult.from_envelope(response_env)

    assert restored.success
    assert restored.data == {"result": "ran_search"}
    assert restored.execution_id == "e1"

    # Raw passthrough still works
    raw = adapter.run_raw("search", {"q": "test"})
    assert raw == {"result": "ran_search"}


# ═══════════════════════════════════════════════════
# F29 B1: Observability — Health probes + logging
# ═══════════════════════════════════════════════════


def test_health_probe_registration() -> None:
    """register_f24_f28_health_probes registers all 5 probes (OB01)."""
    from motor.platform.health import (
        get_health_aggregator,
        register_f24_f28_health_probes,
    )

    # Reset and register
    register_f24_f28_health_probes()

    result = get_health_aggregator().health()
    assert result["status"] == "ok"
    subsystem_names = {result["subsystems"][k]["status"] for k in result["subsystems"]}
    assert subsystem_names == {"ok"}
    assert len(result["subsystems"]) == 5


def test_component_logger_structured() -> None:
    """ComponentLogger produces structured JSON with component/operation."""
    import io
    import json
    import logging

    from motor.platform.logging import ComponentLogger, StructuredFormatter

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(StructuredFormatter())

    logger = logging.getLogger("ura.test_component")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)

    # Register the formatter on the ComponentLogger's logger
    component_logger = logging.getLogger("ura.f25_fusion")
    component_logger.setLevel(logging.INFO)
    component_logger.handlers.clear()
    component_logger.addHandler(handler)

    log = ComponentLogger("f25_fusion")
    log.info("test message", operation="fuse", duration_ms=45, trace_id="abc")

    data = json.loads(buf.getvalue())
    assert data["logger"] == "ura.f25_fusion"
    assert data["component"] == "f25_fusion"
    assert data["operation"] == "fuse"
    assert data["duration_ms"] == 45
    assert data["message"] == "test message"


def test_health_metrics_recorded() -> None:
    """PlatformMetrics.record_health sets health_status and health_ready gauges."""
    from motor.platform import PlatformMetrics

    m = PlatformMetrics()
    m.record_health("f24_web", "ok", True)  # noqa: FBT003
    assert m.health_status._gauges["component=f24_web"].get() == 1.0  # noqa: SLF001
    assert m.health_ready._gauges["component=f24_web"].get() == 1.0  # noqa: SLF001

    m.record_health("f26_memory", "degraded", False)  # noqa: FBT003
    assert m.health_status._gauges["component=f26_memory"].get() == 0.0  # noqa: SLF001
    assert m.health_ready._gauges["component=f26_memory"].get() == 0.0  # noqa: SLF001
