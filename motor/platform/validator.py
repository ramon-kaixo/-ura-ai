"""ProtocolValidator — centralized validation for all protocol invariants."""

from __future__ import annotations

from motor.platform.models import DeliverySemantics, MessageKind, ProtocolEnvelope
from motor.platform.serializer import compute_checksum, verify_checksum


class ProtocolValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class ProtocolValidator:
    """All protocol validation in one place."""

    MAX_PAYLOAD_SIZE = 10 * 1024 * 1024

    def validate(self, envelope: ProtocolEnvelope) -> None:
        self._validate_version(envelope)
        self._validate_routing(envelope)
        self._validate_trace(envelope)
        self._validate_delivery(envelope)
        self._validate_payload(envelope)
        self._validate_checksum_integrity(envelope)

    def _validate_version(self, envelope: ProtocolEnvelope) -> None:
        v = envelope.version
        parts = v.protocol_version.split(".")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ProtocolValidationError(
                "invalid_version", f"protocol_version must be MAJOR.MINOR: {v.protocol_version}"
            )
        sv = v.schema_version.split(".")
        if len(sv) != 2 or not sv[0].isdigit() or not sv[1].isdigit():
            raise ProtocolValidationError(
                "invalid_schema", f"schema_version must be MAJOR.MINOR: {v.schema_version}"
            )
        if v.payload_type not in ("json", "msgpack", "protobuf"):
            raise ProtocolValidationError(
                "invalid_payload_type", f"Unknown payload_type: {v.payload_type}"
            )

    def _validate_routing(self, envelope: ProtocolEnvelope) -> None:
        r = envelope.routing
        if not r.message_type:
            raise ProtocolValidationError("empty_type", "message_type is required")
        if not r.source or not r.destination:
            raise ProtocolValidationError(
                "invalid_routing", "source and destination are required"
            )
        # MessageKind validation: check via .value which works for
        # programmatic construction. Deserialization errors are
        # caught by _from_dict in serializer.py.
        if not isinstance(r.message_kind, MessageKind):
            raise ProtocolValidationError(
                "invalid_kind", f"Unknown message_kind: {r.message_kind}"
            )

    def _validate_trace(self, envelope: ProtocolEnvelope) -> None:
        t = envelope.trace
        if not t.correlation_id.value:
            raise ProtocolValidationError("missing_correlation", "correlation_id is required")

    def _validate_delivery(self, envelope: ProtocolEnvelope) -> None:
        d = envelope.delivery
        if not isinstance(d.semantics, DeliverySemantics):
            raise ProtocolValidationError(
                "invalid_semantics", f"Unknown delivery semantics: {d.semantics}"
            )
        if d.semantics == DeliverySemantics.EXACTLY_ONCE and d.idempotency_key is None:
            raise ProtocolValidationError(
                "missing_idempotency", "EXACTLY_ONCE requires idempotency_key"
            )
        if d.timeout_ms < 0:
            raise ProtocolValidationError("invalid_timeout", "timeout_ms must be >= 0")

    def _validate_payload(self, envelope: ProtocolEnvelope) -> None:
        if len(envelope.payload) > self.MAX_PAYLOAD_SIZE:
            raise ProtocolValidationError(
                "oversized", f"Payload exceeds {self.MAX_PAYLOAD_SIZE} bytes"
            )

    def _validate_checksum_integrity(self, envelope: ProtocolEnvelope) -> None:
        if not envelope.checksum:
            raise ProtocolValidationError("missing_checksum", "checksum is required")
        if not verify_checksum(envelope.payload, envelope.checksum):
            raise ProtocolValidationError(
                "checksum_mismatch",
                f"Checksum {envelope.checksum} does not match payload",
            )

    def validate_checksum(self, payload: bytes, expected: str) -> None:
        if not verify_checksum(payload, expected):
            raise ProtocolValidationError(
                "checksum_mismatch", f"Expected {expected}, got {compute_checksum(payload)}"
            )



