"""Interfaz de almacén de secretos."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ISecretStore(Protocol):
    """Contrato para obtener secretos (API keys, tokens)."""

    def get_secret(self, name: str, default: str | None = None) -> str | None: ...
