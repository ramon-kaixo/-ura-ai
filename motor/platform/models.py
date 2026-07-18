"""Platform Protocols (F28) — models.

All immutable. All deterministic. Thread-safe by design.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

# ── Value Objects ──────────────────────────


@dataclass(frozen=True)
class MessageId:
    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def make(
        cls,
        protocol_version: str,
        schema_version: str,
        source: str,
        destination: str,
        message_type: str,
        payload_first_bytes: bytes,
    ) -> MessageId:
        """Creates a deterministic message ID.

        Uses only the first 64 bytes of payload (O(1), not O(n)).
        This is a deliberate optimization: the first bytes provide
        enough entropy for collision resistance. Full payload would
        make message_id computation O(n) for large payloads without
        meaningful collision-resistance improvement, given SHA-256[:16].
        """
        window = payload_first_bytes[:64]
        raw = f"{protocol_version}:{schema_version}:{source}:{destination}:{message_type}:{window.hex()}"
        return cls(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16])


@dataclass(frozen=True)
class CorrelationId:
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CausationId:
    value: str
    is_root: bool = False

    ROOT_SENTINEL = "ROOT"

    def __str__(self) -> str:
        return self.ROOT_SENTINEL if self.is_root else self.value

    @classmethod
    def root(cls) -> CausationId:
        return cls(value="", is_root=True)

    @classmethod
    def from_string(cls, s: str) -> CausationId:
        if s == cls.ROOT_SENTINEL:
            return cls.root()
        return cls(value=s)


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __str__(self) -> str:
        return self.value


# ── Enums ──────────────────────────────────


class MessageKind(StrEnum):
    COMMAND = "command"
    QUERY = "query"
    EVENT = "event"
    RESPONSE = "response"
    ERROR = "error"


class DeliverySemantics(StrEnum):
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


# ── Headers ────────────────────────────────


@dataclass(frozen=True)
class VersionHeader:
    protocol_version: str = "1.0"
    schema_version: str = "1.0"
    payload_type: str = "json"
    capabilities: tuple[str, ...] = ()
    reserved: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoutingHeader:
    message_id: MessageId
    message_type: str
    message_kind: MessageKind
    source: str
    destination: str


@dataclass(frozen=True)
class TraceHeader:
    correlation_id: CorrelationId
    causation_id: CausationId
    timestamp: float = 0.0


@dataclass(frozen=True)
class DeliveryHeader:
    semantics: DeliverySemantics = DeliverySemantics.AT_MOST_ONCE
    idempotency_key: IdempotencyKey | None = None
    timeout_ms: int = 30000
    cancelable: bool = False
    max_response_bytes: int = 10 * 1024 * 1024
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SecurityHeader:
    auth_token: str | None = None
    auth_token_type: str | None = None


# ── RetryPolicy ────────────────────────────


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_base_ms: int = 100
    backoff_multiplier: float = 2.0
    max_backoff_ms: int = 30000
    retryable_errors: tuple[str, ...] = ("timeout", "transient", "unavailable")


# ── ProtocolEnvelope ────────────────────────


@dataclass(frozen=True)
class ProtocolEnvelope:
    version: VersionHeader
    routing: RoutingHeader
    trace: TraceHeader
    delivery: DeliveryHeader
    payload: bytes = b""
    checksum: str = ""
    security: SecurityHeader | None = None


# ── ErrorEnvelope ──────────────────────────


@dataclass(frozen=True)
class ErrorEnvelope:
    error_code: str
    error_message: str
    error_details: tuple[tuple[str, str], ...] = ()
    component: str = ""
    original_message_id: str = ""
    original_message_type: str = ""
    retryable: bool = False
    retry_delay_ms: int = 0
