"""QualitySourceScorer + SourceScoringStage.

Puntúa fuentes según calidad (autoridad, frescura, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage
from motor.core.fusion.base import SourceScorer as SourceScorerABC
from motor.core.fusion.engine import FusionStage
from motor.core.fusion.models import SourceScore

if TYPE_CHECKING:
    from motor.core.fusion.models import EvidenceSet, FusionContext, KnowledgeClaim


class QualitySourceScorer(SourceScorerABC):
    """Puntúa claims según la calidad de su fuente.

    Usa atributos del Evidence asociado para calcular:
    - Authority: según TLD del documento fuente
    - Freshness: según fetched_at (exponencial decreciente)
    - overall: combinación lineal

    Placeholder para valores que requieren info de WebDocument
    (corroboration, internal_consistency, citation_quality).
    """

    _TLD_WEIGHTS: dict[str, float] = {
        "gov": 0.9, "edu": 0.8, "org": 0.6,
        "io": 0.55, "com": 0.5, "net": 0.5,
    }

    def score(self, claim: KnowledgeClaim) -> SourceScore:
        ev = claim.evidence
        url = ev.document_url if ev else "unknown"
        authority = self._score_authority(url)
        freshness = self._score_freshness(ev.fetched_at if ev else 0)
        overall = (authority * 0.5 + freshness * 0.5)
        return SourceScore(
            url=url,
            authority=authority,
            freshness=freshness,
            overall=overall,
        )

    def score_evidence(self, evidence_set: EvidenceSet) -> list[SourceScore]:
        return [self.score(c) for c in evidence_set.claims]

    @classmethod
    def _score_authority(cls, url: str) -> float:
        tld = cls._parse_tld(url)
        return cls._TLD_WEIGHTS.get(tld, 0.5)

    @staticmethod
    def _parse_tld(url: str) -> str:
        parts = url.split("/")
        if len(parts) >= 3:
            domain = parts[2].lower()
            return domain.rsplit(".", 1)[-1] if "." in domain else "unknown"
        return "unknown"

    @staticmethod
    def _score_freshness(fetched_at: float) -> float:
        import time
        days_old = (time.time() - fetched_at) / 86400.0
        return max(0.1, 1.0 - days_old / 365.0)


class SourceScoringStage(BaseStage):
    """Asigna SourceScore a cada Claim usando un SourceScorer."""

    def __init__(self, scorer: SourceScorerABC | None = None) -> None:
        self._scorer = scorer or QualitySourceScorer()

    @property
    def stage(self) -> FusionStage:
        return FusionStage.SOURCE_SCORING

    @property
    def name(self) -> str:
        return "SourceScoringStage"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _execute(self, context: FusionContext) -> FusionContext:
        for claim in context.claims:
            claim.source_score = self._scorer.score(claim)
        context.statistics["claims_scored"] = len(context.claims)
        context.provenance.source_scorer_name = "QualitySourceScorer"
        context.provenance.source_scorer_version = "1.0.0"
        return context
