"""ProtocolRegistry — registry of schema versions and capabilities."""

from __future__ import annotations

import threading


class ProtocolRegistry:
    """Registry of supported protocol versions, schema versions, and capabilities.

    Thread-safe. No global state (instantiated, not singleton).
    """

    def __init__(self) -> None:
        self._protocol_versions: set[str] = set()
        self._schema_versions: dict[str, set[str]] = {}
        self._capabilities: set[str] = set()
        self._message_types: dict[str, str] = {}
        self._lock = threading.Lock()

    def register_protocol_version(self, version: str) -> None:
        with self._lock:
            self._protocol_versions.add(version)

    def register_schema_version(self, message_type: str, version: str) -> None:
        with self._lock:
            self._schema_versions.setdefault(message_type, set()).add(version)

    def register_capability(self, capability: str) -> None:
        with self._lock:
            self._capabilities.add(capability)

    def register_message_type(self, message_type: str, schema_version: str) -> None:
        with self._lock:
            self._message_types[message_type] = schema_version
            self.register_schema_version(message_type, schema_version)

    def supports_protocol(self, version: str) -> bool:
        return version in self._protocol_versions

    def supports_message_type(self, message_type: str) -> bool:
        return message_type in self._message_types

    def get_schema_version(self, message_type: str) -> str | None:
        return self._message_types.get(message_type)

    def supports_capability(self, capability: str) -> bool:
        return capability in self._capabilities

    @property
    def protocol_versions(self) -> set[str]:
        return set(self._protocol_versions)

    @property
    def message_types(self) -> dict[str, str]:
        return dict(self._message_types)
