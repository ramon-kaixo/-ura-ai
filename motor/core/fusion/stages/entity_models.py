"""Entity Resolution avanzado (F25-B3).

ContextualEntityResolver con desambiguación por contexto,
LRU cache (solo entradas no ambiguas), registro inyectable
y estrategia de scoring sustituible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# ── Modelo de definición de entidad ──────────────────────


@dataclass
class EntityDef:
    """Definición de una entidad conocida.

    Separada del resolver para permitir almacenamiento externo
    (BD, vector DB, archivo YAML) sin modificar el algoritmo.
    """

    entity_id: str
    canonical_name: str
    category: str = ""
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


# ── CachePolicy ─────────────────────────────────────────


class CachePolicy(StrEnum):
    """Política de caché del resolver.

    Valores:
    - DETERMINISTIC_ONLY: solo cachea entradas no ambiguas
      (1 sola definición o UNKNOWN). Las multi-entry no se cachean.
    - ALL: cachea todo, incluyendo el contexto en la clave.
    - DISABLED: sin caché.

    La conversión desde string es case-sensitive (los valores del enum
    están en minúscula). Usar from_string() para conversión segura.
    """

    DETERMINISTIC_ONLY = "deterministic_only"
    ALL = "all"
    DISABLED = "disabled"

    @classmethod
    def from_string(cls, value: str) -> CachePolicy:
        """Convierte una cadena a CachePolicy.

        Case-sensitive. Lanza ValueError si la cadena no es válida.
        """
        try:
            return cls(value)
        except ValueError as err:
            valid = ", ".join(f"'{m.value}'" for m in cls)
            msg = f"Invalid cache policy: '{value}'. Valid values: {valid}"
            raise ValueError(msg) from err


# ── Registro de entidades (inyectable) ───────────────────
