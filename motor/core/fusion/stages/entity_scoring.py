"""Entity Resolution avanzado (F25-B3).

ContextualEntityResolver con desambiguación por contexto,
LRU cache (solo entradas no ambiguas), registro inyectable
y estrategia de scoring sustituible.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from motor.core.fusion.stages.entity_models import EntityDef

# ── Modelo de definición de entidad ──────────────────────


@dataclass
class ScoringStrategy(ABC):
    """Estrategia de desambiguación sustituible.

    Contrato formal:

    Precondiciones:
    - entries: lista de 2 o más EntityDef (el resolver maneja 1 directamente).
    - context: texto plano, no vacío. El scorer aplica su propia normalización.
    - entries son inmutables durante la llamada.

    Postcondiciones:
    - Retorna int ∈ [0, len(entries)) → la entrada ganadora.
    - Retorna None → ambiguo (no se pudo decidir, o hay empate).

    Empates:
    - Si dos o más entradas obtienen la misma puntuación máxima,
      debe retornar None. No desempatar arbitrariamente.
    - La única excepción es si la implementación incorpora un criterio
      de desempate documentado (ej: orden alfabético, prioridad por categoría).

    Determinismo:
    - Mismas entradas + mismo contexto → mismo resultado (o None).
    - El scorer no debe depender de estado externo mutable.

    Rango de puntuación:
    - Interno a cada implementación. No se requiere normalización.
    - Para fines de auditoría, la puntuación de cada entrada puede
      exponerse vía atributo adicional en la implementación concreta.

    La implementación por defecto (KeywordScorer) usa conteo de keywords.
    Puede reemplazarse por embeddings, TF-IDF, o LLM sin modificar la pipeline.
    """

    @abstractmethod
    def select(self, entries: list[EntityDef], context: str) -> int | None:
        """Selecciona la mejor entrada entre múltiples candidatas.

        Solo se invoca cuando hay 2 o más entradas (el resolver maneja
        el caso de 1 entrada directamente, sin ambigüedad).

        Args:
            entries: Lista de 2 o más EntityDef inmutables durante la llamada.
            context: Texto completo del claim (sin normalizar).

        Returns:
            int: índice en entries de la mejor candidata.
            None: ambiguo (no se puede decidir, empate, o ninguna es válida).

        """
        ...


class KeywordScorer(ScoringStrategy):
    """Puntúa cada entrada contando keywords presentes en el contexto.

    Si hay empate o ninguna keyword coincide → None (AMBIGUOUS).
    """

    def select(self, entries: list[EntityDef], context: str) -> int | None:
        if len(entries) == 1:
            return 0
        ctx_lower = context.lower()
        scores = [sum(1 for kw in e.keywords if kw in ctx_lower) for e in entries]
        max_score = max(scores)
        if max_score == 0 or scores.count(max_score) > 1:
            return None
        return scores.index(max_score)


# ── Registro por defecto ─────────────────────────────────

