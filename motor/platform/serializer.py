"""Protocol serializers — canonical, deterministic JSON encoding."""

from __future__ import annotations

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
    RoutingHeader,
    SecurityHeader,
    TraceHeader,
    VersionHeader,
)

# ── ABCs ───────────────────────────────────


class ProtocolSerializer(ABC):
    @abstractmethod
    def serialize(self, envelope: ProtocolEnvelope) -> bytes:
        """Serialize envelope to bytes (canonical JSON)."""
        ...


class ProtocolDeserializer(ABC):
    @abstractmethod
    def deserialize(self, data: bytes) -> ProtocolEnvelope:
        """Deserialize bytes to ProtocolEnvelope."""
        ...


# ── Implementation ────────────────────────


_DEFAULT_ENCODING = "utf-8"


def _to_dict(envelope: ProtocolEnvelope) -> dict[str, Any]:
    v = envelope.version
    r = envelope.routing
    t = envelope.trace
    d = envelope.delivery
    s = envelope.security

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
            "correlation_id": str(t.correlation_id),
            "causation_id": str(t.causation_id),
            "timestamp": t.timestamp,
        },
        "delivery": {
            "semantics": d.semantics.value,
            "timeout_ms": d.timeout_ms,
            "cancelable": d.cancelable,
            "max_response_bytes": d.max_response_bytes,
        },
        "payload_hex": envelope.payload.hex(),
    }

    if d.idempotency_key is not None:
        result["delivery"]["idempotency_key"] = str(d.idempotency_key)

    if d.metadata:
        result["delivery"]["metadata"] = dict(d.metadata)

    if s is not None:
        sec: dict[str, Any] = {}
        if s.auth_token is not None:
            sec["auth_token"] = s.auth_token
            sec["auth_token_type"] = s.auth_token_type or "bearer"
        if sec:
            result["security"] = sec

    return result


def _from_dict(data: dict[str, Any]) -> ProtocolEnvelope:
    v = data["version"]
    r = data["routing"]
    t = data["trace"]
    d = data["delivery"]

    payload_hex = data.get("payload_hex", "")
    payload = bytes.fromhex(payload_hex) if payload_hex else b""

    metadata = d.get("metadata", {}) or {}

    ik = d.get("idempotency_key")
    idempotency_key = IdempotencyKey(ik) if ik else None

    security_data = data.get("security")
    security = None
    if security_data:
        security = SecurityHeader(
            auth_token=security_data.get("auth_token"),
            auth_token_type=security_data.get("auth_token_type"),
        )

    return ProtocolEnvelope(
        version=VersionHeader(
            protocol_version=v["protocol_version"],
            schema_version=v["schema_version"],
            payload_type=v.get("payload_type", "json"),
            capabilities=tuple(v.get("capabilities", [])),
            reserved=tuple(v.get("reserved", [])),
        ),
        routing=RoutingHeader(
            message_id=MessageId(r["message_id"]),
            message_type=r["message_type"],
            message_kind=MessageKind(r["message_kind"]),
            source=r["source"],
            destination=r["destination"],
        ),
        trace=TraceHeader(
            correlation_id=CorrelationId(t["correlation_id"]),
            causation_id=CausationId(t.get("causation_id", "")),
            timestamp=t.get("timestamp", 0.0),
        ),
        delivery=DeliveryHeader(
            semantics=DeliverySemantics(d["semantics"]),
            idempotency_key=idempotency_key,
            timeout_ms=d.get("timeout_ms", 30000),
            cancelable=d.get("cancelable", False),
            max_response_bytes=d.get("max_response_bytes", 10 * 1024 * 1024),
            metadata=metadata,  # type: ignore
        ),
        payload=payload,
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


def make_message_id(
    protocol_version: str,
    schema_version: str,
    source: str,
    destination: str,
    message_type: str,
    payload: bytes,
) -> MessageId:
    first_64 = payload[:64]
    return MessageId.make(
        protocol_version, schema_version,
        source, destination, message_type,
        first_64,
    )
