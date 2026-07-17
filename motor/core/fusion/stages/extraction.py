"""ExtractionStage: convierte Evidence en KnowledgeClaim."""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage
from motor.core.fusion.engine import FusionStage
from motor.core.fusion.models import KnowledgeClaim, make_claim_id

if TYPE_CHECKING:
    from motor.core.fusion.models import FusionContext


class ExtractionStage(BaseStage):
    """Convierte cada Evidence en un KnowledgeClaim.

    Cada claim conserva el evidence_id como id base, el fragment como
    text, quality_score como confidence inicial, y el objeto Evidence.
    """

    @property
    def stage(self) -> FusionStage:
        return FusionStage.EXTRACTION

    @property
    def name(self) -> str:
        return "ExtractionStage"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _execute(self, context: FusionContext) -> FusionContext:
        bundle = context.bundle
        if bundle is None:
            return context

        claims: list[KnowledgeClaim] = []
        for ev in bundle.evidence:
            claim = KnowledgeClaim(
                id=make_claim_id(ev.evidence_id, ev.fragment),
                text=ev.fragment,
                confidence=ev.quality_score,
                evidence=ev,
                created_at=ev.fetched_at,
                text_id=ev.evidence_id,
            )
            claims.append(claim)

        context.claims = claims
        context.statistics["claims_extracted"] = len(claims)
        return context
