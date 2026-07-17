"""MemoryCandidateSelectionStage + ThresholdSelector.

Selección de Facts como candidatos para memoria.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage, MemoryCandidateSelector
from motor.core.fusion.engine import FusionStage

if TYPE_CHECKING:
    from motor.core.fusion.models import FusionContext, FusionResult, KnowledgeFact


class ThresholdSelector(MemoryCandidateSelector):
    """Filtra Facts por confianza mínima y límite de cantidad."""

    def __init__(self, min_confidence: float = 0.3, max_candidates: int = 100) -> None:
        self.min_confidence = min_confidence
        self.max_candidates = max_candidates

    def select(
        self,
        fusion_result: FusionResult,
        max_candidates: int = 100,
    ) -> list[KnowledgeFact]:
        m = min(max_candidates, self.max_candidates)
        selected = [
            f for f in fusion_result.accepted
            if f.confidence >= self.min_confidence
        ]
        selected.sort(key=lambda f: f.confidence, reverse=True)
        return selected[:m]


class MemoryCandidateSelectionStage(BaseStage):
    """Selecciona facts candidatos para memoria persistente.

    Placeholder: en B3+ se consultará el MemoryStore para evitar
    duplicados y detectar cambios.
    """

    def __init__(self, selector: MemoryCandidateSelector | None = None) -> None:
        self._selector = selector or ThresholdSelector()

    @property
    def stage(self) -> FusionStage:
        return FusionStage.SELECTION

    @property
    def name(self) -> str:
        return "MemoryCandidateSelectionStage"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _execute(self, context: FusionContext) -> FusionContext:
        ambiguous_ids = context.statistics.get("ambiguous_entity_ids", [])
        if ambiguous_ids:
            context.warnings.append(
                f"Memory selection skipping {len(ambiguous_ids)} ambiguous entities"
            )

        context.statistics["candidates_requested"] = self._selector.max_candidates
        context.statistics["candidates_returned"] = 0
        context.provenance.selector_name = "ThresholdSelector"
        context.provenance.selector_version = "1.0.0"
        return context
