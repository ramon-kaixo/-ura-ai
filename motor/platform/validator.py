"""ProtocolValidator — centralized validation for all protocol invariants."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from motor.platform.models import DeliverySemantics, MessageKind, ProtocolEnvelope
from motor.platform.registry import ProtocolRegistry
from motor.platform.serializer import compute_checksum, verify_checksum

if TYPE_CHECKING:
    from motor.platform.metrics import PlatformMetrics

logger = logging.getLogger("ura.security")


class ProtocolValidationError(Exception):
    def __init__(self, code: str, message: str, envelope: ProtocolEnvelope | None = None) -> None:
        self.code = code
        self.message = message
        self.envelope = envelope
        if envelope is not None and code not in ("invalid_version", "invalid_schema"):
            logger.warning(
                "SECURITY: %s from=%s to=%s type=%s msg=%s",
                code, envelope.routing.source, envelope.routing.destination,
                envelope.routing.message_type, message,
            )
        super().__init__(f"[{code}] {message}")


class ProtocolValidator:
    """All protocol validation and sanitization in one place."""

    MAX_PAYLOAD_SIZE = 10 * 1024 * 1024

    def __init__(
        self, registry: ProtocolRegistry | None = None,
        metrics: PlatformMetrics | None = None,
    ) -> None:
        self._registry = registry
        self._metrics = metrics

    # Size budgets per message type per ADR-028-04
    SIZE_BUDGETS: dict[str, int] = {
        "ToolRequest": 1 * 1024 * 1024,
        "ToolResult": 10 * 1024 * 1024,
        "MemoryEntry": 10 * 1024 * 1024,
        "AgentAuditRecord": 1 * 1024 * 1024,
        "Event": 100 * 1024,
    }
    # ProtocolEnvelope headers budget: 1 KB (not enforced per-message_type,
    # covered by the total serialized size check)

    FORBIDDEN_PATTERNS = [
        b"<script", b"javascript:", b"onload=", b"onerror=",
        b"../", b"..\\", b"${", b"`",
    ]

    def _sanitize_payload(self, envelope: ProtocolEnvelope) -> None:
        """Busca patrones peligrosos en el payload."""
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in envelope.payload.lower():
                raise ProtocolValidationError(
                    "unsafe_payload",
                    f"Payload contains forbidden pattern: {pattern[:20]}",
                )

    def validate(self, envelope: ProtocolEnvelope) -> None:
        start = time.monotonic()
        self._validate_version(envelope)
        self._validate_routing(envelope)
        self._validate_trace(envelope)
        self._validate_delivery(envelope)
        self._validate_payload(envelope)
        self._validate_checksum_integrity(envelope)
        self._validate_schema_compatibility(envelope)
        self._sanitize_payload(envelope)
        if self._metrics is not None:
            try:
                ms = (time.monotonic() - start) * 1000
                self._metrics.record_validation(source=envelope.routing.source, duration_ms=ms)
            except Exception:
                logger.debug("Metrics record_validation failed", exc_info=True)

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
        if not t.trace_id.value:
            raise ProtocolValidationError("missing_trace", "trace_id is required (OBS-01)")
        if not t.span_id.value:
            raise ProtocolValidationError("missing_span", "span_id is required (OBS-03)")

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
        payload_len = len(envelope.payload)
        if payload_len > self.MAX_PAYLOAD_SIZE:
            raise ProtocolValidationError(
                "oversized", f"Payload {payload_len} exceeds global max {self.MAX_PAYLOAD_SIZE} bytes"
            )
        # Per-message-type size budget (ADR-028-04)
        for prefix, budget in self.SIZE_BUDGETS.items():
            if envelope.routing.message_type.startswith(prefix):
                if payload_len > budget:
                    raise ProtocolValidationError(
                        "oversized",
                        f"Payload {payload_len} exceeds {budget} budget for {prefix}",
                    )
                break

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

    def _validate_schema_compatibility(self, envelope: ProtocolEnvelope) -> None:
        """Verify the recipient can deserialize this message's schema.

        Per ADR-028-01/S04 and ADR-028-04/4.2:
        Recipient must support MAJOR ≤ its schema_version for the message_type.
        """
        if self._registry is None:
            return
        msg_type = envelope.routing.message_type
        schema_version = envelope.version.schema_version
        supported = self._registry.get_schema_version(msg_type)
        if supported is None:
            return
        # Parse versions
        try:
            sv_maj = int(schema_version.split(".")[0])
            sp_maj = int(supported.split(".")[0])
        except (ValueError, IndexError):
            return
        if sv_maj > sp_maj:
            raise ProtocolValidationError(
                "schema_mismatch",
                f"Schema {schema_version} for {msg_type} requires MAJOR ≤ {supported}",
            )



