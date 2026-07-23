"""Protocol serializers — canonical, deterministic JSON encoding."""

from __future__ import annotations

import gzip
import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

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

# ── Compression helpers (ADR-028-04 SR05-SR07) ────────

SUPPORTED_COMPRESSION = {"gzip", "zstd", "none"}


def compress_payload(data: bytes, method: str = "gzip") -> bytes:
    if method == "gzip":
        return gzip.compress(data)
    if method == "zstd":
        msg = "zstd compression not yet available"
        raise NotImplementedError(msg)
    if method == "none":
        return data
    msg = f"Unsupported compression: {method}"
    raise ValueError(msg)


def decompress_payload(data: bytes, method: str = "gzip") -> bytes:
    if method == "gzip":
        return gzip.decompress(data)
    if method == "zstd":
        msg = "zstd decompression not yet available"
        raise NotImplementedError(msg)
    if method == "none":
        return data
    msg = f"Unsupported compression: {method}"
    raise ValueError(msg)


# ── Serializers ──────────────────────────


class ProtocolSerializer(ABC):
    @abstractmethod
    def serialize(self, envelope: ProtocolEnvelope) -> bytes: ...


class ProtocolDeserializer(ABC):
    @abstractmethod
    def deserialize(self, data: bytes) -> ProtocolEnvelope: ...


_DEFAULT_ENCODING = "utf-8"


def _metadata_to_tuple(md: dict[str, str] | tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
    if isinstance(md, dict):
        return tuple(sorted(md.items()))
    return md


def _to_dict(envelope: ProtocolEnvelope) -> dict[str, Any]:
    v, r, t, d, s = envelope.version, envelope.routing, envelope.trace, envelope.delivery, envelope.security

    result: dict[str, Any] = {
        "version": {
            "protocol_version": v.protocol_version,
            "schema_version": v.schema_version,
            "payload_type": v.payload_type,
            "capabilities": list(v.capabilities),
            "reserved": list(v.reserved),
        },
        "routing": {
            "message_id": str(r.message_id),
            "message_type": r.message_type,
            "message_kind": r.message_kind.value,
            "source": r.source,
            "destination": r.destination,
        },
        "trace": {
            "trace_id": str(t.trace_id),
            "span_id": str(t.span_id),
            "parent_span_id": str(t.parent_span_id) if t.parent_span_id else "",
            "correlation_id": str(t.correlation_id) if t.correlation_id else "",
            "causation_id": str(t.causation_id) if t.causation_id else "",
            "timestamp": t.timestamp,
            "monotonic_ts": t.monotonic_ts,
        },
        "delivery": {
            "semantics": d.semantics.value,
            "timeout_ms": d.timeout_ms,
            "cancelable": d.cancelable,
            "max_response_bytes": d.max_response_bytes,
        },
        "payload_hex": envelope.payload.hex(),
        "checksum": envelope.checksum,
    }

    if d.idempotency_key is not None:
        result["delivery"]["idempotency_key"] = str(d.idempotency_key)

    if d.metadata:
        result["delivery"]["metadata"] = [list(pair) for pair in d.metadata]

    if d.retry_policy is not None:
        rp = d.retry_policy
        result["delivery"]["retry_policy"] = {
            "max_attempts": rp.max_attempts,
            "backoff_base_ms": rp.backoff_base_ms,
            "backoff_multiplier": rp.backoff_multiplier,
            "max_backoff_ms": rp.max_backoff_ms,
            "retryable_errors": list(rp.retryable_errors),
        }

    if s is not None:
        sec: dict[str, Any] = {}
        if s.auth_token is not None:
            sec["auth_token"] = s.auth_token
            sec["auth_token_type"] = s.auth_token_type or "bearer"
        if sec:
            result["security"] = sec

    return result


def _from_dict(data: dict[str, Any]) -> ProtocolEnvelope:
    vd = data["version"]
    rd = data["routing"]
    td = data["trace"]
    dd = data["delivery"]

    payload_hex = data.get("payload_hex", "")
    raw_payload = bytes.fromhex(payload_hex) if payload_hex else b""
    checksum = data.get("checksum", "")
    if checksum and not verify_checksum(raw_payload, checksum):
        msg = f"Checksum mismatch: expected {checksum}, got {compute_checksum(raw_payload)}"
        raise ProtocolException(msg)

    # Payload stays as-is (compressed if wire format was compressed).
    # ADR-028-04 SR05: envelope payload is compressed, checksum covers compressed bytes.
    # Application consumers check payload_type and decompress if needed.
    payload = raw_payload

    metadata_raw = dd.get("metadata", []) or []
    metadata = tuple(tuple(pair) for pair in metadata_raw) if metadata_raw else ()

    ik_str = dd.get("idempotency_key")
    idempotency_key = IdempotencyKey(ik_str) if ik_str else None

    rp_raw = dd.get("retry_policy")
    if rp_raw:
        retry_policy = RetryPolicy(
            max_attempts=rp_raw.get("max_attempts", 3),
            backoff_base_ms=rp_raw.get("backoff_base_ms", 100),
            backoff_multiplier=rp_raw.get("backoff_multiplier", 2.0),
            max_backoff_ms=rp_raw.get("max_backoff_ms", 30000),
            retryable_errors=tuple(rp_raw.get("retryable_errors", [])),
        )
    else:
        retry_policy = None

    # CausationId — use from_string to preserve root sentinel
    causation = CausationId.from_string(td.get("causation_id", ""))

    # Trace fields
    trace_id = TraceId(td.get("trace_id", TraceId.generate().value))
    span_id = SpanId(td.get("span_id", SpanId.generate().value))
    parent_raw = td.get("parent_span_id", "")
    parent_span_id = SpanId(parent_raw) if parent_raw else None
    corr_id_raw = td.get("correlation_id", "")
    correlation_id = CorrelationId(corr_id_raw) if corr_id_raw else None

    # MessageKind — catch unknown values for forwarding to dead-letter
    try:
        message_kind = MessageKind(rd["message_kind"])
    except ValueError:
        msg = f"Unknown message_kind: {rd.get('message_kind', '')}"
        raise ProtocolException(msg)  # noqa: B904

    security_data = data.get("security")
    security = None
    if security_data:
        security = SecurityHeader(
            auth_token=security_data.get("auth_token"),
            auth_token_type=security_data.get("auth_token_type"),
        )

    return ProtocolEnvelope(
        version=VersionHeader(
            protocol_version=vd.get("protocol_version", "1.0"),
            schema_version=vd.get("schema_version", "1.0"),
            payload_type=vd.get("payload_type", "json"),
            capabilities=tuple(vd.get("capabilities", [])),
            reserved=tuple(vd.get("reserved", [])),
        ),
        routing=RoutingHeader(
            message_id=MessageId(rd["message_id"]),
            message_type=rd.get("message_type", ""),
            message_kind=message_kind,
            source=rd.get("source", ""),
            destination=rd.get("destination", ""),
        ),
        trace=TraceHeader(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            correlation_id=correlation_id,
            causation_id=causation,
            timestamp=td.get("timestamp", 0.0),
            monotonic_ts=td.get("monotonic_ts", 0),
        ),
        delivery=DeliveryHeader(
            semantics=DeliverySemantics(dd.get("semantics", "at_most_once")),
            idempotency_key=idempotency_key,
            timeout_ms=dd.get("timeout_ms", 30000),
            cancelable=dd.get("cancelable", False),
            max_response_bytes=dd.get("max_response_bytes", 10 * 1024 * 1024),
            metadata=metadata,
            retry_policy=retry_policy,
        ),
        payload=payload,
        checksum=checksum,
        security=security,
    )


class JsonProtocolSerializer(ProtocolSerializer):
    """Canonical JSON serializer. Deterministic. sort_keys=True."""

    def serialize(self, envelope: ProtocolEnvelope) -> bytes:
        raw = json.dumps(
            _to_dict(envelope),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return raw.encode(_DEFAULT_ENCODING)


class JsonProtocolDeserializer(ProtocolDeserializer):
    """Deserializes canonical JSON to ProtocolEnvelope."""

    def deserialize(self, data: bytes) -> ProtocolEnvelope:
        raw = data.decode(_DEFAULT_ENCODING)
        parsed = json.loads(raw)
        return _from_dict(parsed)


def compute_checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_checksum(payload: bytes, expected: str) -> bool:
    return compute_checksum(payload) == expected


def make_envelope_with_checksum(
    version: VersionHeader,
    routing: RoutingHeader,
    trace: TraceHeader,
    delivery: DeliveryHeader,
    payload: bytes = b"",
    security: SecurityHeader | None = None,
    compression: str = "none",
) -> ProtocolEnvelope:
    """Creates a ProtocolEnvelope with payload checksum pre-computed.

    If compression != "none", the payload is compressed before storage and
    the payload_type in VersionHeader is updated to reflect compression.
    Per ADR-028-04 SR05: compression BEFORE checksum.
    """
    compressed = compress_payload(payload, method=compression)
    cs = compute_checksum(compressed)

    # Update payload_type to reflect compression
    base_type = version.payload_type
    if compression != "none" and not base_type.endswith(f"+{compression}"):
        version = VersionHeader(
            protocol_version=version.protocol_version,
            schema_version=version.schema_version,
            payload_type=f"{base_type}+{compression}",
            capabilities=version.capabilities,
            reserved=version.reserved,
        )

    return ProtocolEnvelope(
        version=version,
        routing=routing,
        trace=trace,
        delivery=delivery,
        payload=compressed,
        checksum=cs,
        security=security,
    )


def make_message_id(
    protocol_version: str,
    schema_version: str,
    source: str,
    destination: str,
    message_type: str,
    payload: bytes,
) -> MessageId:
    """Deterministic message ID.

    Uses only the first 64 bytes of payload (constant-time window).
    This is deliberate: full-payload ID would make message_id
    computation O(n) for large payloads. The 64-byte window provides
    sufficient entropy for SHA-256[:16] collision resistance.
    """
    first_64 = payload[:64]
    return MessageId.make(
        protocol_version,
        schema_version,
        source,
        destination,
        message_type,
        first_64,
    )
