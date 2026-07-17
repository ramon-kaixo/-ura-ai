"""KnowledgeMergerStage + SimpleKnowledgeMerger.

Fusión de Claims en Facts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage, KnowledgeMerger
from motor.core.fusion.engine import FusionStage

if TYPE_CHECKING:
    from motor.core.fusion.models import (
        Conflict,
        FusionContext,
        KnowledgeClaim,
        KnowledgeFact,
    )


class SimpleKnowledgeMerger(KnowledgeMerger):
    """Convierte Claims en Facts (1 claim → 1 fact).

    Placeholder: en B3+ se agruparán Claims por entidad resuelta.
    """

    @property
    def version(self) -> str:
        return "1.0.0"

    def merge(
        self,
        claims: list[KnowledgeClaim],
        conflicts: list[Conflict],
    ) -> list[KnowledgeFact]:
        from motor.core.fusion.models import KnowledgeFact, make_fact_id

        facts: list[KnowledgeFact] = []
        for claim in claims:
            words = claim.text.split()
            subject = words[0] if words else ""
            predicate = words[1] if len(words) > 1 else ""
            obj = " ".join(words[2:]) if len(words) > 2 else ""
            confidence = claim.confidence
            provenance = (claim.id,)
            eids = (claim.text_id,) if claim.text_id else ()

            fid = make_fact_id(subject, predicate, obj)

            fact = KnowledgeFact(
                id=fid,
                subject=subject,
                predicate=predicate,
                object=obj,
                confidence=confidence,
                provenance=provenance,
                evidence_ids=eids,
            )
            facts.append(fact)

        return facts


class KnowledgeMergerStage(BaseStage):
    """Ejecuta el KnowledgeMerger para fusionar claims en facts."""

    def __init__(self, merger: KnowledgeMerger | None = None) -> None:
        self._merger = merger or SimpleKnowledgeMerger()

    @property
    def stage(self) -> FusionStage:
        return FusionStage.MERGE

    @property
    def name(self) -> str:
        return "KnowledgeMergerStage"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _execute(self, context: FusionContext) -> FusionContext:
        facts = self._merger.merge(
            context.claims or [],
            context.conflicts or [],
        )
        context.facts = facts
        context.statistics["facts_merged"] = len(facts)
        context.provenance.merger_name = "SimpleKnowledgeMerger"
        context.provenance.merger_version = "1.0.0"
        return context
