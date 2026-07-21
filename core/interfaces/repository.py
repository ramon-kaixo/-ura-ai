"""Interfaz de almacén vectorial."""

from __future__ import annotations

from typing import Protocol


class IVectorStore(Protocol):
    """Contrato para almacenamiento y consulta vectorial."""

    def guardar_incidente(self, incidente: dict) -> bool: ...

    def buscar_similares(self, vector: list[float], limite: int = 5) -> list[dict]: ...
