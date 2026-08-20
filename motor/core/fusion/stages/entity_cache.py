"""Entity Resolution avanzado (F25-B3).

ContextualEntityResolver con desambiguación por contexto,
LRU cache (solo entradas no ambiguas), registro inyectable
y estrategia de scoring sustituible.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from motor.core.fusion.models import ResolvedEntity

# ── Modelo de definición de entidad ──────────────────────


@dataclass
class LRUCache:
    """Cache LRU para resoluciones deterministas.

    Solo almacena entradas cuya resolución NO depende del contexto:
    - Entidades con una única definición (no ambiguas)
    - Resultados UNKNOWN

    Las entidades ambiguas (múltiples definiciones) NO se cachean
    para evitar falsos aciertos cuando el contexto cambia.
    """

    def __init__(self, maxsize: int = 2048) -> None:
        self._cache: OrderedDict[str, ResolvedEntity] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> ResolvedEntity | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, entity: ResolvedEntity) -> None:
        self._cache[key] = entity
        self._cache.move_to_end(key)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def clear(self) -> None:
        self._cache.clear()


# ── Funciones auxiliares ─────────────────────────────────


