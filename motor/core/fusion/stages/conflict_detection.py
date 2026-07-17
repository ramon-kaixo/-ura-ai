"""NaiveConflictResolver + ConflictDetectionStage.

Detección de contradicciones basada en reglas simples (sin IA).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage, ConflictResolver
from motor.core.fusion.engine import FusionStage
from motor.core.fusion.models import Conflict, ConflictGraph, ConflictType, KnowledgeFact, make_conflict_id

if TYPE_CHECKING:
    from motor.core.fusion.models import FusionContext, KnowledgeClaim


class NaiveConflictResolver(ConflictResolver):
    """Detecta contradicciones entre Claims que comparten sujeto y predicado
    pero difieren en el objeto.

    Resolución: el Claim con mayor confidence prevalece.
    Si hay empate, ambos se marcan como no resueltos.
    """

    @property
    def version(self) -> str:
        return "1.0.0"

    def detect(self, claims: list[KnowledgeClaim]) -> list[Conflict]:
        buckets: dict[tuple[str, str], list[KnowledgeClaim]] = {}
        for c in claims:
            key = (c.subject.lower(), c.predicate.lower())
            buckets.setdefault(key, []).append(c)

        conflicts: list[Conflict] = []
        for bucket in buckets.values():
            for i, a in enumerate(bucket):
                for b in bucket[i + 1:]:
                    conflict = self._check_pair(a, b)
                    if conflict is not None:
                        conflicts.append(conflict)
        return conflicts

    def resolve(
        self,
        conflicts: list[Conflict],
        claims: list[KnowledgeClaim],
    ) -> tuple[list[KnowledgeFact], list[Conflict]]:
        resolved_facts: list[KnowledgeFact] = []
        unresolved: list[Conflict] = []
        claim_map = {c.id: c for c in claims}

        for conflict in conflicts:
            ca = claim_map.get(conflict.claim_a)
            cb = claim_map.get(conflict.claim_b)
            if ca is None or cb is None:
                continue
            if abs(ca.confidence - cb.confidence) > 0.2:
                winner = ca if ca.confidence > cb.confidence else cb
                conflict.resolved = True
                conflict.resolution = (
                    f"Preferring claim {winner.id} (confidence={winner.confidence:.2f})"
                )
            else:
                unresolved.append(conflict)

        return resolved_facts, unresolved

    @staticmethod
    def _check_pair(a: KnowledgeClaim, b: KnowledgeClaim) -> Conflict | None:
        if not a.subject or not b.subject:
            return None
        if a.subject.lower() != b.subject.lower():
            return None
        if a.predicate.lower() != b.predicate.lower():
            return None
        if a.object.lower() == b.object.lower():
            return None

        ctype = ConflictType.CONTRADICTION
        cid = make_conflict_id(a.id, b.id, ctype.value)
        return Conflict(
            id=cid,
            claim_a=a.id,
            claim_b=b.id,
            conflict_type=ctype,
            description=f"'{a.object}' vs '{b.object}' for {a.subject}/{a.predicate}",
        )


class ConflictDetectionStage(BaseStage):
    """Etapa que detecta y resuelve conflictos entre Claims."""

    def __init__(self, resolver: ConflictResolver | None = None) -> None:
        self._resolver = resolver or NaiveConflictResolver()

    @property
    def stage(self) -> FusionStage:
        return FusionStage.CONFLICT_DETECTION

    @property
    def name(self) -> str:
        return "ConflictDetectionStage"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _execute(self, context: FusionContext) -> FusionContext:
        if not context.claims:
            return context

        ambiguous_ids = context.statistics.get("ambiguous_entity_ids", [])
        if ambiguous_ids:
            context.warnings.append(
                f"Skipping conflict detection for {len(ambiguous_ids)} ambiguous entities"
            )

        claims_to_check = [
            c for c in context.claims
            if not any(aid in (c.text + c.normalized_text) for aid in ambiguous_ids)
        ] if ambiguous_ids else context.claims

        if not claims_to_check:
            context.statistics["conflicts_detected"] = 0
            context.statistics["conflicts_unresolved"] = 0
            return context

        conflicts = self._resolver.detect(claims_to_check)
        _, unresolved = self._resolver.resolve(conflicts, claims_to_check)
        context.conflicts = unresolved
        context.conflict_graph = ConflictGraph.from_edges(conflicts)
        context.statistics["conflicts_detected"] = len(conflicts)
        context.statistics["conflicts_unresolved"] = len(unresolved)
        context.provenance.conflict_resolver_name = "NaiveConflictResolver"
        context.provenance.conflict_resolver_version = self._resolver.version
        return context
