"""BasicChangeDetector + KnowledgeDeltaStage.

Detección de cambios entre facts nuevos y existentes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage, ChangeDetector
from motor.core.fusion.engine import FusionStage

if TYPE_CHECKING:
    from motor.core.fusion.models import FusionContext, KnowledgeDelta, KnowledgeFact


class BasicChangeDetector(ChangeDetector):
    """Compara entity_id + statement para clasificar cambios.

    Un fact nuevo es ADDED si su entity_id no existe en existing.
    UPDATED si mismo entity_id, statement diferente.
    CONFIRMED si mismo entity_id, misma statement.

    Placeholder: detección semántica real en B3+.
    """

    @property
    def version(self) -> str:
        return "1.0.0"

    def detect_delta(
        self,
        new_facts: list[KnowledgeFact],
        existing_facts: list[KnowledgeFact],
    ) -> KnowledgeDelta:
        from motor.core.fusion.models import KnowledgeDelta

        existing_by_id: dict[str, KnowledgeFact] = {}
        for f in existing_facts:
            if f.id:
                existing_by_id[f.id] = f

        added: list[KnowledgeFact] = []
        updated: list[KnowledgeFact] = []
        confirmed: list[KnowledgeFact] = []

        for fact in new_facts:
            existing = existing_by_id.get(fact.id)
            if existing is None:
                added.append(fact)
            elif fact.object != existing.object:
                updated.append(fact)
            else:
                confirmed.append(fact)

        return KnowledgeDelta(
            facts_added=tuple(added),
            facts_updated=tuple(updated),
            facts_removed=(),
        )


class KnowledgeDeltaStage(BaseStage):
    """Genera deltas comparando facts nuevos vs existentes.

    Los existing_facts se pasan como field adicional en statistics
    bajo 'candidate_facts', o se leen de context.facts si no hay
    candidatos externos.
    """

    def __init__(self, detector: ChangeDetector | None = None) -> None:
        self._detector = detector or BasicChangeDetector()

    @property
    def stage(self) -> FusionStage:
        return FusionStage.DELTA_DETECTION

    @property
    def name(self) -> str:
        return "KnowledgeDeltaStage"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _execute(self, context: FusionContext) -> FusionContext:
        new_facts = context.facts or []
        existing_facts = context.statistics.get("existing_facts", [])
        delta = self._detector.detect_delta(new_facts, existing_facts)
        context.statistics["deltas_added"] = len(delta.facts_added)
        context.statistics["deltas_updated"] = len(delta.facts_updated)
        context.statistics["deltas_removed"] = len(delta.facts_removed)
        context.statistics["has_changes"] = delta.has_changes
        context.provenance.change_detector_name = "BasicChangeDetector"
        context.provenance.change_detector_version = "1.0.0"
        return context
