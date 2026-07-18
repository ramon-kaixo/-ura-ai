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
    IdempotencyKey,
    JsonProtocolDeserializer,
    JsonProtocolSerializer,
    MessageId,
    MessageKind,
    ProtocolEnvelope,
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
    r = RoutingHeader(message_id=mid, message_type=message_type, message_kind=kind, source=source, destination=destination)
    t = TraceHeader(trace_id=TraceId.generate(), span_id=SpanId.generate(), correlation_id=CorrelationId(correlation), causation_id=CausationId.root(), timestamp=1000.0)
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
    assert ':' in data  # compact separators
    assert '"payload_hex"' in data


def test_serialization_with_security() -> None:
    env = _make_env()
    sec = SecurityHeader(auth_token="tok123", auth_token_type="bearer")
    env2 = make_envelope_with_checksum(version=env.version, routing=env.routing, trace=env.trace, delivery=env.delivery, payload=env.payload, security=sec)
    ser = JsonProtocolSerializer()
    deser = JsonProtocolDeserializer()
    data = ser.serialize(env2)
    restored = deser.deserialize(data)
    assert restored.security is not None
    assert restored.security.auth_token == "tok123"


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
    t = TraceHeader(trace_id=TraceId(""), span_id=SpanId(""), correlation_id=CorrelationId(""), causation_id=CausationId.root())
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
    rng = random.Random(42)
    deser = JsonProtocolDeserializer()
    for _ in range(100):
        length = rng.randint(1, 500)
        junk = bytes(rng.randint(0, 255) for _ in range(length))
        try:
            deser.deserialize(junk)
        except Exception:
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
        version=env.version, routing=env.routing, trace=env.trace,
        delivery=env.delivery, payload=b"tampered", checksum=env.checksum,
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
    bad_data = json.dumps({
        "version": {"protocol_version": "1.0", "schema_version": "1.0",
                     "payload_type": "json", "capabilities": [], "reserved": []},
        "routing": {"message_id": "x", "message_type": "T",
                     "message_kind": "UNKNOWN_FUTURE_KIND",
                     "source": "s", "destination": "d"},
        "trace": {"correlation_id": "c", "causation_id": "ROOT", "timestamp": 0},
        "delivery": {"semantics": "at_most_once", "timeout_ms": 30000,
                      "cancelable": False, "max_response_bytes": 10000000},
        "payload_hex": "", "checksum": "",
    }).encode()
    with pytest.raises(ProtocolException):
        deser.deserialize(bad_data)


# ═══════════════════════════════════════════════════
# B2.15: Metadata immutable (CR-08)
# ═══════════════════════════════════════════════════


def test_metadata_is_immutable() -> None:
    dh = DeliveryHeader(metadata=(("key", "value"),))
    assert isinstance(dh.metadata, tuple)
    assert dh.metadata == (("key", "value"),)
