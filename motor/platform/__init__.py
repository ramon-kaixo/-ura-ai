"""Platform Protocols (F28).

Infraestructura de comunicación entre subsistemas.
Independiente del transporte. Sin dependencias de HTTP, RPC ni colas.

API Classification:
- 🟢 ESTABLE: ProtocolEnvelope, VersionHeader, RoutingHeader,
    TraceHeader, DeliveryHeader, SecurityHeader, ErrorEnvelope,
    MessageId, CorrelationId, CausationId, MessageKind,
    DeliverySemantics, ProtocolValidator, ProtocolSerializer,
    ProtocolDeserializer, Transport, CompatibilityChecker,
    VersionNegotiator, SpanId, TraceId
- 🟡 ADVANCED: ProtocolRegistry, RetryPolicy, IdempotencyKey,
    LocalTransport, ProtocolException, ProtocolValidationError,
    TraceContext, TraceExporter, MetricsCollector, TraceMiddleware,
    HealthAggregator, SpanEvent
- 🔵 INTERNA: compute_checksum, verify_checksum, make_message_id,
    make_envelope_with_checksum
"""

from motor.platform.compat import CompatibilityChecker
from motor.platform.errors import ProtocolException
from motor.platform.health import HealthAggregator, get_health_aggregator
from motor.platform.middleware import TraceMiddleware, traced
from motor.platform.models import (
    CausationId,
    CorrelationId,
    DeliveryHeader,
    DeliverySemantics,
    ErrorEnvelope,
    IdempotencyKey,
    MessageId,
    MessageKind,
    ProtocolEnvelope,
    RetryPolicy,
    RoutingHeader,
    SecurityHeader,
    SpanId,
    TraceHeader,
    TraceId,
    VersionHeader,
)
from motor.platform.negotiator import VersionNegotiationResult, VersionNegotiator
from motor.platform.registry import ProtocolRegistry
from motor.platform.serializer import (
    JsonProtocolDeserializer,
    JsonProtocolSerializer,
    ProtocolDeserializer,
    ProtocolSerializer,
    compute_checksum,
    make_envelope_with_checksum,
    make_message_id,
    verify_checksum,
)
from motor.platform.tracing import (
    MetricsCollector,
    SpanEvent,
    TraceContext,
    TraceExporter,
    get_metrics_collector,
    record_latency,
)
from motor.platform.transport import LocalTransport, Transport
from motor.platform.validator import ProtocolValidationError, ProtocolValidator

__all__ = [
    "CausationId",
    "CompatibilityChecker",
    "CorrelationId",
    "DeliveryHeader",
    "DeliverySemantics",
    "ErrorEnvelope",
    "HealthAggregator",
    "IdempotencyKey",
    "JsonProtocolDeserializer",
    "JsonProtocolSerializer",
    "LocalTransport",
    "MessageId",
    "MessageKind",
    "MetricsCollector",
    "ProtocolDeserializer",
    "ProtocolEnvelope",
    "ProtocolException",
    "ProtocolRegistry",
    "ProtocolSerializer",
    "ProtocolValidationError",
    "ProtocolValidator",
    "RetryPolicy",
    "RoutingHeader",
    "SecurityHeader",
    "SpanEvent",
    "SpanId",
    "TraceContext",
    "TraceExporter",
    "TraceHeader",
    "TraceId",
    "TraceMiddleware",
    "Transport",
    "VersionHeader",
    "VersionNegotiationResult",
    "VersionNegotiator",
    "compute_checksum",
    "get_health_aggregator",
    "get_metrics_collector",
    "make_envelope_with_checksum",
    "make_message_id",
    "record_latency",
    "traced",
    "verify_checksum",
]
