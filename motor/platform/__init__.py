"""Platform Protocols (F28) — preserved modules."""

from motor.platform.models import (
    CausationId,
    CorrelationId,
    DeliveryHeader,
    DeliverySemantics,
    ErrorCode,
    IdempotencyKey,
    MessageId,
    MessageKind,
    ProtocolEnvelope,
    ProtocolException,
    RoutingHeader,
    SpanId,
    TraceHeader,
    TraceId,
    VersionHeader,
)
from motor.platform.resilience import Backpressure, CircuitBreaker
from motor.platform.serializer import (
    JsonProtocolDeserializer,
    JsonProtocolSerializer,
    compute_checksum,
    make_envelope_with_checksum,
    make_message_id,
    verify_checksum,
)

__all__ = [
    "Backpressure",
    "CausationId",
    "CircuitBreaker",
    "CorrelationId",
    "DeliveryHeader",
    "DeliverySemantics",
    "ErrorCode",
    "IdempotencyKey",
    "JsonProtocolDeserializer",
    "JsonProtocolSerializer",
    "MessageId",
    "MessageKind",
    "ProtocolEnvelope",
    "ProtocolException",
    "RoutingHeader",
    "SpanId",
    "TraceHeader",
    "TraceId",
    "VersionHeader",
    "compute_checksum",
    "make_envelope_with_checksum",
    "make_message_id",
    "verify_checksum",
]
