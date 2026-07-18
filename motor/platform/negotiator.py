"""VersionNegotiation — per-message-kind version negotiation."""

from __future__ import annotations

from motor.platform.models import MessageKind


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
    """Negotiates protocol version per message kind."""

    MIN_EVENT_VERSION = "1.0"

    def negotiate(
        self,
        emitter_version: str,
        receiver_version: str,
        emitter_capabilities: set[str],
        receiver_capabilities: set[str],
        kind: MessageKind,
    ) -> VersionNegotiationResult:
        em_maj, em_min = _parse_major_minor(emitter_version)
        rc_maj, rc_min = _parse_major_minor(receiver_version)

        if emitter_version == receiver_version:
            caps = emitter_capabilities & receiver_capabilities
            return VersionNegotiationResult(
                protocol_version=emitter_version,
                schema_version=emitter_version,
                capabilities=frozenset(caps),
                compatible=True,
            )

        # MAJOR mismatch
        if em_maj != rc_maj:
            if kind in (MessageKind.EVENT,):
                # EVENT: dead-letter if emitter is newer
                # EVENT: reject if receiver is newer
                if em_maj > rc_maj:
                    return VersionNegotiationResult(
                        protocol_version=emitter_version,
                        schema_version=emitter_version,
                        capabilities=frozenset(),
                        compatible=False,
                    )
                return VersionNegotiationResult(
                    protocol_version=receiver_version,
                    schema_version=receiver_version,
                    capabilities=frozenset(),
                    compatible=False,
                )

            # COMMAND/QUERY: reject with version_mismatch
            return VersionNegotiationResult(
                protocol_version=emitter_version,
                schema_version=emitter_version,
                capabilities=frozenset(),
                compatible=False,
            )

        # Same MAJOR, different MINOR → use lower MINOR
        negotiated_min = min(em_min, rc_min)
        negotiated_ver = f"{em_maj}.{negotiated_min}"
        negotiated_schema = f"{em_maj}.{negotiated_min}"
        caps = emitter_capabilities & receiver_capabilities

        return VersionNegotiationResult(
            protocol_version=negotiated_ver,
            schema_version=negotiated_schema,
            capabilities=frozenset(caps),
            compatible=True,
        )

    def negotiate_event(
        self,
        emitter_version: str,
        receiver_version: str,
    ) -> VersionNegotiationResult:
        return self.negotiate(
            emitter_version, receiver_version,
            set(), set(), MessageKind.EVENT,
        )
