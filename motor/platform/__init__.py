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

from motor.platform.audit import AuditLogger
from motor.platform.compat import CompatibilityChecker
from motor.platform.delivery import ErrorDelivery, classify_error  # noqa: F401
from motor.platform.errors import ProtocolException
from motor.platform.health import HealthAggregator, get_health_aggregator
from motor.platform.metrics import PlatformMetrics, get_platform_metrics  # noqa: F401
from motor.platform.middleware import TraceMiddleware, traced
from motor.platform.models import (
    CausationId,
    CorrelationId,
    DeliveryHeader,
    DeliverySemantics,
    ErrorCode,
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
    DropPolicy,
    InMemoryExporter,
    MetricsCollector,
    Sampler,
    SamplingStrategy,
    SpanEvent,
    SpanTreeError,
    TraceContext,
    TraceExporter,
    get_metrics_collector,
    record_latency,
    sanitize_tags,
    validate_span_tree,
)
from motor.platform.transport import LocalTransport, Transport
from motor.platform.validator import ProtocolValidationError, ProtocolValidator

__all__ = [
    "AuditLogger",
    "CausationId",
    "CompatibilityChecker",
    "CorrelationId",
    "DeliveryHeader",
    "DeliverySemantics",
    "DropPolicy",
    "ErrorCode",
    "ErrorDelivery",
    "ErrorEnvelope",
    "HealthAggregator",
    "IdempotencyKey",
    "InMemoryExporter",
    "JsonProtocolDeserializer",
    "JsonProtocolSerializer",
    "LocalTransport",
    "MessageId",
    "MessageKind",
    "MetricsCollector",
    "PlatformMetrics",
    "ProtocolDeserializer",
    "ProtocolEnvelope",
    "ProtocolException",
    "ProtocolRegistry",
    "ProtocolSerializer",
    "ProtocolValidationError",
    "ProtocolValidator",
    "RetryPolicy",
    "RoutingHeader",
    "Sampler",
    "SamplingStrategy",
    "SecurityHeader",
    "SpanEvent",
    "SpanId",
    "SpanTreeError",
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
    "sanitize_tags",
    "traced",
    "validate_span_tree",
    "verify_checksum",
]
