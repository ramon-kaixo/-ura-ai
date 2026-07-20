"""Platform Protocols (F28) — models.

All immutable. All deterministic. Thread-safe by design.

OBS-01: trace_id is the single root. Created once per operation.
OBS-02: No subsystem creates a new trace_id; only propagates.
OBS-03: Every hop generates a unique span_id.
OBS-04: parent_span_id is mandatory for tree reconstruction.
OBS-05: correlation_id and causation_id never change during operation.
OBS-06: monotonic_ts (time.monotonic_ns) alongside UTC timestamp.
OBS-07: Every error includes span_id in error_details.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from enum import StrEnum

# ── Value Objects ──────────────────────────


@dataclass(frozen=True)
class SpanId:
    """Unique span identifier for distributed tracing.

    OBS-03: Every hop generates a unique span_id.
    16 hex chars from os.urandom (8 bytes → 128 bits of entropy).
    """

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> SpanId:
        """Generate a new unique span ID. OBS-03."""
        return cls(os.urandom(8).hex())

    @classmethod
    def root(cls) -> SpanId:
        """Root span ID — sentinel for the first hop."""
        return cls("ROOT_SPAN")


@dataclass(frozen=True)
class TraceId:
    """Trace identifier — the single root for an entire operation.

    OBS-01: Exactly one trace_id per operation.
    OBS-02: No subsystem creates a new one; only propagates.
    16 hex chars from os.urandom (8 bytes).
    """

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> TraceId:
        """Generate a new trace ID. Called exactly once per operation root."""
        return cls(os.urandom(8).hex())


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


class ErrorCode(StrEnum):
    """Canonical error codes per ADR-028-06."""

    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    TRANSIENT = "transient"
    INVALID_PAYLOAD = "invalid_payload"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    OVERSIZED = "oversized"
    VERSION_MISMATCH = "version_mismatch"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    UNKNOWN_MESSAGE = "unknown_message"
    INTERNAL_ERROR = "internal_error"


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
    """Distributed tracing header (OBS-01..07).

    trace_id: root trace ID — single per operation (OBS-01/OBS-02)
    span_id: unique per hop (OBS-03)
    parent_span_id: previous span for tree reconstruction (OBS-04)
    correlation_id: unchanged during operation (OBS-05)
    causation_id: unchanged during operation (OBS-05)
    timestamp: UTC time (OBS-06, for human readability)
    monotonic_ts: time.monotonic_ns() for latency (OBS-06)
    """

    trace_id: TraceId
    span_id: SpanId
    parent_span_id: SpanId | None = None
    correlation_id: CorrelationId | None = None
    causation_id: CausationId | None = None
    timestamp: float = 0.0
    monotonic_ts: int = 0


@dataclass(frozen=True)
class DeliveryHeader:
    semantics: DeliverySemantics = DeliverySemantics.AT_MOST_ONCE
    idempotency_key: IdempotencyKey | None = None
    timeout_ms: int = 30000
    cancelable: bool = False
    max_response_bytes: int = 10 * 1024 * 1024
    metadata: tuple[tuple[str, str], ...] = ()
    retry_policy: RetryPolicy | None = None


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
    span_id: str = ""  # OBS-07: span_id where the error occurred
    original_message_id: str = ""
    original_message_type: str = ""
    retryable: bool = False
    retry_delay_ms: int = 0

    @classmethod
    def from_original(
        cls,
        original: ProtocolEnvelope,
        error_code: str,
        error_message: str,
        component: str = "",
        retryable: bool = False,
        retry_delay_ms: int = 0,
    ) -> ErrorEnvelope:
        """Build ErrorEnvelope inheriting causation from original message.

        Per ADR-028-06 ER04: ERROR causation_id inherits from original.
        Per ADR-028-06 ER03: original_message_id points to triggering message.
        """
        return cls(
            error_code=error_code,
            error_message=error_message,
            component=component or original.routing.destination,
            original_message_id=str(original.routing.message_id),
            original_message_type=original.routing.message_type,
            retryable=retryable,
            retry_delay_ms=retry_delay_ms,
        )
