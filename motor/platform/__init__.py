"""Platform Protocols (F28).

Infraestructura de comunicación entre subsistemas.
Independiente del transporte. Sin dependencias de HTTP, RPC ni colas.
"""

from motor.platform.compat import CompatibilityChecker
from motor.platform.errors import ProtocolException
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
    TraceHeader,
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
from motor.platform.transport import LocalTransport, Transport
from motor.platform.validator import ProtocolValidationError, ProtocolValidator

__all__ = [
    "CausationId",
    "CompatibilityChecker",
    "CorrelationId",
    "DeliveryHeader",
    "DeliverySemantics",
    "ErrorEnvelope",
    "IdempotencyKey",
    "JsonProtocolDeserializer",
    "JsonProtocolSerializer",
    "LocalTransport",
    "MessageId",
    "MessageKind",
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
    "TraceHeader",
    "Transport",
    "VersionHeader",
    "VersionNegotiationResult",
    "VersionNegotiator",
    "compute_checksum",
    "make_envelope_with_checksum",
    "make_message_id",
    "verify_checksum",
]
