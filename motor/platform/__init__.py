"""Platform Protocols (F28) — preserved modules."""

from motor.platform.models import (  # noqa: F401
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
from motor.platform.resilience import Backpressure, CircuitBreaker  # noqa: F401
from motor.platform.serializer import (  # noqa: F401
    JsonProtocolDeserializer,
    JsonProtocolSerializer,
    compute_checksum,
    make_envelope_with_checksum,
    make_message_id,
    verify_checksum,
)
