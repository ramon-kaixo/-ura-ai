"""VersionNegotiation — per-message-kind version negotiation."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from motor.platform.models import MessageKind

if TYPE_CHECKING:
    from motor.platform.metrics import PlatformMetrics


class VersionNegotiationResult:
    def __init__(
        self,
        protocol_version: str,
        schema_version: str,
        capabilities: frozenset[str],
        compatible: bool,
    ) -> None:
        self.protocol_version = protocol_version
        self.schema_version = schema_version
        self.capabilities = capabilities
        self.compatible = compatible


def _parse_major_minor(version: str) -> tuple[int, int]:
    parts = version.split(".")
    return int(parts[0]), int(parts[1])


class VersionNegotiator:
    """Negotiates protocol version per message kind.

    Optionally instruments negotiation latency via PlatformMetrics.
    """

    MIN_EVENT_VERSION = "1.0"

    def __init__(self, metrics: PlatformMetrics | None = None) -> None:
        self._metrics = metrics

    def negotiate(
        self,
        emitter_version: str,
        receiver_version: str,
        emitter_capabilities: set[str],
        receiver_capabilities: set[str],
        kind: MessageKind,
    ) -> VersionNegotiationResult:
        start = time.monotonic()
        em_maj, em_min = _parse_major_minor(emitter_version)
        rc_maj, rc_min = _parse_major_minor(receiver_version)

        if emitter_version == receiver_version:
            caps = emitter_capabilities & receiver_capabilities
            result = VersionNegotiationResult(
                protocol_version=emitter_version,
                schema_version=emitter_version,
                capabilities=frozenset(caps),
                compatible=True,
            )
        elif em_maj != rc_maj:
            if kind == MessageKind.EVENT:
                if em_maj > rc_maj:
                    result = VersionNegotiationResult(
                        protocol_version=emitter_version,
                        schema_version=emitter_version,
                        capabilities=frozenset(),
                        compatible=False,
                    )
                else:
                    result = VersionNegotiationResult(
                        protocol_version=receiver_version,
                        schema_version=receiver_version,
                        capabilities=frozenset(),
                        compatible=False,
                    )
            else:
                result = VersionNegotiationResult(
                    protocol_version=emitter_version,
                    schema_version=emitter_version,
                    capabilities=frozenset(),
                    compatible=False,
                )
        else:
            negotiated_min = min(em_min, rc_min)
            caps = emitter_capabilities & receiver_capabilities
            result = VersionNegotiationResult(
                protocol_version=f"{em_maj}.{negotiated_min}",
                schema_version=f"{em_maj}.{negotiated_min}",
                capabilities=frozenset(caps),
                compatible=True,
            )

        if self._metrics is not None:
            try:
                ms = (time.monotonic() - start) * 1000
                self._metrics.record_negotiation(emitter_version, receiver_version, ms)
            except Exception:
                logging.getLogger("ura.platform.negotiator").debug(
                    "Metrics record_negotiation failed", exc_info=True,
                )
        return result

    def negotiate_event(
        self,
        emitter_version: str,
        receiver_version: str,
    ) -> VersionNegotiationResult:
        return self.negotiate(
            emitter_version, receiver_version,
            set(), set(), MessageKind.EVENT,
        )

    def negotiate_response(
        self,
        trigger_version: str,
        emitter_capabilities: set[str],
        receiver_capabilities: set[str],
    ) -> VersionNegotiationResult:
        """RESPONSE inherits protocol_version from the triggering COMMAND/QUERY.

        Per ADR-028-03: RESPONSE uses the same version as the request.
        No separate negotiation. Same MAJOR required.
        """
        return self.negotiate(
            trigger_version, trigger_version,
            emitter_capabilities, receiver_capabilities,
            MessageKind.RESPONSE,
        )

    def negotiate_error(
        self,
        original_message_version: str,
        emitter_capabilities: set[str],
        receiver_capabilities: set[str],
    ) -> VersionNegotiationResult:
        """ERROR inherits protocol_version from the original message.

        Per ADR-028-03: ERROR uses the same version as the message
        that caused it. No separate negotiation.
        """
        return self.negotiate(
            original_message_version, original_message_version,
            emitter_capabilities, receiver_capabilities,
            MessageKind.ERROR,
        )
