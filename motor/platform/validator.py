"""Validator for protocol envelopes — payload sanitization and safety checks."""

from __future__ import annotations

from motor.platform.models import ProtocolEnvelope

_UNSAFE_PATTERNS = [b"<script", b"javascript:", b"onerror=", b"onload="]


class ProtocolValidator:
    """Validates ProtocolEnvelope payloads for safety and integrity."""

    def validate(self, envelope: ProtocolEnvelope) -> None:
        """Validate envelope payload. Raises ValueError if unsafe content found."""
        payload = getattr(envelope, "payload", None) or getattr(envelope, "checksum", b"")
        if isinstance(payload, bytes):
            for pat in _UNSAFE_PATTERNS:
                if pat in payload.lower():
                    msg = f"unsafe_payload: pattern '{pat.decode()}' detected"
                    raise ValueError(msg)
