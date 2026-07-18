"""MemoryCandidateSelectionStage + ThresholdSelector.

Selecciona Facts y los escribe en F26 Memory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage, MemoryCandidateSelector
from motor.core.fusion.engine import FusionStage

if TYPE_CHECKING:
    from motor.core.fusion.models import FusionContext, KnowledgeFact
# Importación en tiempo real para FusionResult
from motor.core.fusion.models import FusionResult


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
        from motor.memory import FactRef as MemoryFactRef
        from motor.memory import MemoryEntry, MemoryEventType, make_entry_id

        ambiguous_ids = context.statistics.get("ambiguous_entity_ids", [])
        if ambiguous_ids:
            context.warnings.append(
                f"Memory selection skipping {len(ambiguous_ids)} ambiguous entities"
            )

        # Seleccionar candidatos
        selected = self._selector.select(
            FusionResult(accepted=tuple(context.facts)),
        )

        # Escribir en F26 Memory (si está disponible)
        memory = context.statistics.get("_memory_instance")
        if memory is not None and selected:
            for kf in selected:
                # Crear MemoryEntry con FactRef
                refs = (
                    MemoryFactRef(
                        fact_id=kf.id,
                        version_id=f"v{kf.version}",
                        subject=kf.subject,
                        predicate=kf.predicate,
                        object=kf.object,
                    ),
                )
                entry = MemoryEntry(
                    entry_id=make_entry_id("fact_added", [ref.version_id for ref in refs], kf.created_at or 0.0),
                    timestamp=kf.created_at or 0.0,
                    fact_refs=refs,
                    source="fusion_pipeline",
                    event_type=MemoryEventType.FACT_ADDED,
                )
                try:
                    memory.append(entry)
                except KeyError:
                    continue  # duplicado

        context.statistics["candidates_requested"] = self._selector.max_candidates
        context.statistics["candidates_returned"] = len(selected)
        context.statistics["memory_entries_written"] = len(selected) if memory is not None else 0
        context.provenance.selector_name = "ThresholdSelector"
        context.provenance.selector_version = "1.0.0"
        return context
