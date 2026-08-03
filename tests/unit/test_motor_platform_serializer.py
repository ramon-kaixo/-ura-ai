"""Tests para motor.platform.serializer (ProtocolSerializer, checksums, payloads)."""
from __future__ import annotations

import gzip
import json

import pytest

from motor.platform.models import (
    CausationId,
    CorrelationId,
    DeliveryHeader,
    DeliverySemantics,
    IdempotencyKey,
    MessageId,
    MessageKind,
    ProtocolEnvelope,
    ProtocolException,
    RetryPolicy,
    RoutingHeader,
    SecurityHeader,
    SpanId,
    TraceHeader,
    TraceId,
    VersionHeader,
)
from motor.platform.serializer import (
    JsonProtocolDeserializer,
    JsonProtocolSerializer,
    _metadata_to_tuple,
    compress_payload,
    compute_checksum,
    decompress_payload,
    make_envelope_with_checksum,
    make_message_id,
    verify_checksum,
)

SERIALIZER = JsonProtocolSerializer()
DESERIALIZER = JsonProtocolDeserializer()


def _trace_header(**overrides) -> TraceHeader:
    defaults = dict(
        trace_id=TraceId("trace-1"),
        span_id=SpanId("span-1"),
        parent_span_id=SpanId("parent-1"),
        correlation_id=CorrelationId("corr-1"),
        causation_id=CausationId("caus-1"),
        timestamp=123.5,
        monotonic_ts=456,
    )
    defaults.update(overrides)
    return TraceHeader(**defaults)


def _routing() -> RoutingHeader:
    return RoutingHeader(
        message_id=MessageId("msg-1"),
        message_type="test.type",
        message_kind=MessageKind.COMMAND,
        source="src",
        destination="dst",
    )


def _envelope(**overrides) -> ProtocolEnvelope:
    defaults: dict = dict(
        version=VersionHeader(
            protocol_version="1.0",
            schema_version="2.0",
            payload_type="json",
            capabilities=("a", "b"),
            reserved=("r",),
        ),
        routing=_routing(),
        trace=_trace_header(),
        delivery=DeliveryHeader(
            semantics=DeliverySemantics.EXACTLY_ONCE,
            idempotency_key=IdempotencyKey("ik-1"),
            timeout_ms=5000,
            cancelable=True,
            max_response_bytes=4096,
            metadata=(("k1", "v1"), ("k2", "v2")),
            retry_policy=RetryPolicy(
                max_attempts=5,
                backoff_base_ms=200,
                backoff_multiplier=3.0,
                max_backoff_ms=60000,
                retryable_errors=("timeout",),
            ),
        ),
        payload=b"hola mundo",
        checksum=compute_checksum(b"hola mundo"),
        security=SecurityHeader(auth_token="tok", auth_token_type="bearer"),
    )
    defaults.update(overrides)
    return ProtocolEnvelope(**defaults)


class TestCompression:
    def test_gzip_roundtrip(self):
        data = b"datos" * 100
        compressed = compress_payload(data, "gzip")
        assert compressed != data
        assert decompress_payload(compressed, "gzip") == data

    def test_zstd_raises(self):
        with pytest.raises(NotImplementedError):
            compress_payload(b"x", "zstd")
        with pytest.raises(NotImplementedError):
            decompress_payload(b"x", "zstd")

    def test_none_passthrough(self):
        assert compress_payload(b"x", "none") == b"x"
        assert decompress_payload(b"x", "none") == b"x"

    def test_unsupported_method(self):
        with pytest.raises(ValueError, match="Unsupported compression"):
            compress_payload(b"x", "brotli")
        with pytest.raises(ValueError, match="Unsupported compression"):
            decompress_payload(b"x", "brotli")


class TestMetadataToTuple:
    def test_dict_sorted(self):
        assert _metadata_to_tuple({"b": "2", "a": "1"}) == (("a", "1"), ("b", "2"))

    def test_tuple_passthrough(self):
        md = (("a", "1"), ("b", "2"))
        assert _metadata_to_tuple(md) is md


class TestSerialize:
    def test_serialize_full(self):
        data = SERIALIZER.serialize(_envelope())
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["routing"]["message_id"] == "msg-1"
        assert parsed["trace"]["parent_span_id"] == "parent-1"
        assert parsed["delivery"]["idempotency_key"] == "ik-1"
        assert parsed["delivery"]["retry_policy"]["max_attempts"] == 5
        assert parsed["delivery"]["metadata"] == [["k1", "v1"], ["k2", "v2"]]
        assert parsed["security"]["auth_token"] == "tok"
        assert parsed["payload_hex"] == b"hola mundo".hex()
        assert parsed["version"]["capabilities"] == ["a", "b"]

    def test_serialize_deterministic(self):
        env = _envelope()
        assert SERIALIZER.serialize(env) == SERIALIZER.serialize(env)

    def test_serialize_no_security_omits(self):
        env = _envelope(security=None)
        data = SERIALIZER.serialize(env)
        parsed = json.loads(data.decode("utf-8"))
        assert "security" not in parsed

    def test_serialize_trace_optional_fields(self):
        env = _envelope(
            trace=TraceHeader(
                trace_id=TraceId("t"),
                span_id=SpanId("s"),
                parent_span_id=None,
                correlation_id=None,
                causation_id=None,
            )
        )
        data = SERIALIZER.serialize(env)
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["trace"]["parent_span_id"] == ""
        assert parsed["trace"]["correlation_id"] == ""

    def test_serialize_delivery_minimal(self):
        env = _envelope(
            delivery=DeliveryHeader(
                semantics=DeliverySemantics.AT_MOST_ONCE,
                idempotency_key=None,
                metadata=(),
                retry_policy=None,
            )
        )
        data = SERIALIZER.serialize(env)
        parsed = json.loads(data.decode("utf-8"))
        assert "idempotency_key" not in parsed["delivery"]
        assert "retry_policy" not in parsed["delivery"]
        assert "metadata" not in parsed["delivery"]


class TestDeserialize:
    def test_roundtrip_full(self):
        env = _envelope()
        restored = DESERIALIZER.deserialize(SERIALIZER.serialize(env))
        assert restored == env
        assert restored.payload == b"hola mundo"
        assert restored.checksum == compute_checksum(b"hola mundo")
        assert restored.delivery.metadata == (("k1", "v1"), ("k2", "v2"))
        assert restored.delivery.retry_policy.max_attempts == 5
        assert restored.security.auth_token == "tok"

    def test_roundtrip_minimal(self):
        env = _envelope(
            delivery=DeliveryHeader(semantics=DeliverySemantics.AT_MOST_ONCE),
            trace=TraceHeader(
                trace_id=TraceId("t"), span_id=SpanId("s"), parent_span_id=None, correlation_id=None
            ),
            security=None,
        )
        restored = DESERIALIZER.deserialize(SERIALIZER.serialize(env))
        assert restored.trace.parent_span_id is None
        assert restored.trace.correlation_id is None
        assert restored.security is None
        assert restored.delivery.retry_policy is None

    def test_checksum_mismatch_raises(self):
        env = _envelope(checksum="deadbeef")
        with pytest.raises(ProtocolException, match="Checksum mismatch"):
            DESERIALIZER.deserialize(SERIALIZER.serialize(env))

    def test_unknown_message_kind_raises(self):
        env = _envelope()
        data = SERIALIZER.serialize(env)
        parsed = json.loads(data.decode("utf-8"))
        parsed["routing"]["message_kind"] = "bogus"
        with pytest.raises(ProtocolException, match="Unknown message_kind"):
            DESERIALIZER.deserialize(json.dumps(parsed).encode())

    def test_root_causation_roundtrip(self):
        env = _envelope(
            trace=TraceHeader(
                trace_id=TraceId("t"),
                span_id=SpanId("s"),
                causation_id=CausationId.root(),
            )
        )
        restored = DESERIALIZER.deserialize(SERIALIZER.serialize(env))
        assert restored.trace.causation_id.is_root is True


class TestChecksum:
    def test_compute_and_verify(self):
        payload = b"abc"
        cs = compute_checksum(payload)
        assert verify_checksum(payload, cs) is True
        assert verify_checksum(b"abd", cs) is False


class TestMakeEnvelope:
    def test_none_compression(self):
        env = make_envelope_with_checksum(
            version=VersionHeader(),
            routing=_routing(),
            trace=_trace_header(),
            delivery=DeliveryHeader(),
            payload=b"data",
        )
        assert env.payload == b"data"
        assert env.checksum == compute_checksum(b"data")
        assert env.version.payload_type == "json"

    def test_gzip_compression_updates_payload_type(self):
        env = make_envelope_with_checksum(
            version=VersionHeader(),
            routing=_routing(),
            trace=_trace_header(),
            delivery=DeliveryHeader(),
            payload=b"data",
            compression="gzip",
        )
        assert env.version.payload_type == "json+gzip"
        assert gzip.decompress(env.payload) == b"data"
        assert env.checksum == compute_checksum(env.payload)

    def test_no_duplicate_payload_type_suffix(self):
        env = make_envelope_with_checksum(
            version=VersionHeader(payload_type="json+gzip"),
            routing=_routing(),
            trace=_trace_header(),
            delivery=DeliveryHeader(),
            payload=b"data",
            compression="gzip",
        )
        assert env.version.payload_type == "json+gzip"


class TestMakeMessageId:
    def test_deterministic(self):
        mid = make_message_id("1.0", "1.0", "src", "dst", "type", b"payload")
        assert isinstance(mid, MessageId)
        assert mid == make_message_id("1.0", "1.0", "src", "dst", "type", b"payload")
        assert mid != make_message_id("1.0", "1.0", "src", "dst", "type", b"other")

    def test_only_first_64_bytes_used(self):
        mid_short = make_message_id("1.0", "1.0", "s", "d", "t", b"x" * 64)
        mid_long = make_message_id("1.0", "1.0", "s", "d", "t", b"x" * 200)
        assert mid_short == mid_long
