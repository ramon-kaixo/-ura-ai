"""DocumentRanker — ranking configurable de documentos web (F24-B6)."""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.web.models import WebDocument


@dataclass
class RankingScore:
    """Puntuación descomponible con contribuciones individuales.

    Cada factor puede inspeccionarse por separado, lo que permite
    en fases posteriores (F25, F27) justificar por qué una fuente
    fue priorizada sin modificar el algoritmo de ranking.
    """

    quality: float = 0.0
    position: float = 0.0
    length: float = 0.0
    title_match: float = 0.0
    url_match: float = 0.0
    text_match: float = 0.0
    canonical_bonus: float = 0.0
    short_penalty: float = 0.0
    empty_penalty: float = 0.0

    @property
    def total(self) -> float:
        return round(
            self.quality
            + self.position
            + self.length
            + self.title_match
            + self.url_match
            + self.text_match
            + self.canonical_bonus
            + self.short_penalty
            + self.empty_penalty,
            6,
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "quality": round(self.quality, 4),
            "position": round(self.position, 4),
            "length": round(self.length, 4),
            "title_match": round(self.title_match, 4),
            "url_match": round(self.url_match, 4),
            "text_match": round(self.text_match, 4),
            "canonical_bonus": round(self.canonical_bonus, 4),
            "short_penalty": round(self.short_penalty, 4),
            "empty_penalty": round(self.empty_penalty, 4),
            "total": self.total,
        }


@dataclass
class RankedDocument:
    """Documento con su puntuación final y desglose."""

    document: WebDocument
    score: RankingScore = field(default_factory=RankingScore)

    @property
    def final_score(self) -> float:
        return self.score.total

    @property
    def score_breakdown(self) -> dict[str, float]:
        return self.score.to_dict()


DEFAULT_WEIGHTS: dict[str, float] = {
    "quality": 3.0,
    "position": 2.0,
    "length": 1.0,
    "title_match": 3.0,
    "url_match": 1.5,
    "text_match": 1.0,
    "canonical_bonus": 0.5,
    "short_penalty": -2.0,
    "empty_penalty": -5.0,
}

_SHORT_THRESHOLD = 50
_EMPTY_THRESHOLD = 10


class DocumentRanker:
    """Ranking de documentos basado en factores configurables.

    Factores:
    - quality_score del extractor
    - Posición original en el buscador
    - Longitud del contenido (saturación logarítmica)
    - Coincidencia del término de búsqueda en título, URL, texto
    - Bonus por URL canónica
    - Penalización por contenido corto o casi vacío

    Thread-safe. Ranking estable (empates deshechos por URL).
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self._lock = threading.Lock()

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def rank(
        self,
        query: str,
        documents: list[WebDocument],
        positions: dict[str, int] | None = None,
    ) -> list[RankedDocument]:
        """Ordena documentos según relevancia.

        Args:
            query: Término de búsqueda.
            documents: Documentos a ordenar.
            positions: Mapa URL → posición original en buscador.
        """
        with self._lock:
            result: list[RankedDocument] = []
            query_lower = query.lower().strip()
            terms = [t for t in re.split(r"\W+", query_lower) if t]

            for i, doc in enumerate(documents):
                pos = (positions or {}).get(doc.url, i)
                score = self._compute(doc, query_lower, terms, pos)
                result.append(RankedDocument(document=doc, score=score))

            # Estable: total descendente, URL ascendente como tiebreaker
            result.sort(key=lambda r: (-r.final_score, r.document.url))
            return result

    def _match_count(self, text: str, terms: list[str]) -> int:
        """Cuenta ocurrencias de todos los términos en un texto."""
        return sum(text.count(t) for t in terms)

    def _compute(
        self,
        doc: WebDocument,
        query_lower: str,
        terms: list[str],
        position: int,
    ) -> RankingScore:
        text_lower = (doc.text or "").lower()
        title_lower = (doc.title or "").lower()
        url_lower = doc.url.lower()
        wc = doc.word_count or len((doc.text or "").split())

        quality = doc.quality_score * self._weights["quality"]
        pos_score = (1.0 / (1.0 + position)) * self._weights["position"]

        # longitud con saturación logarítmica
        length_raw = math.log2(1 + wc) / math.log2(1 + 1000)
        length_score = min(1.0, length_raw) * self._weights["length"]

        # coincidencias (cada factor escala para que su máximo = weight)
        title_hits = self._match_count(title_lower, terms)
        title_score = min(3.0, title_hits) * (self._weights["title_match"] / 3.0)

        url_hits = self._match_count(url_lower, terms)
        url_score = min(2.0, url_hits) * (self._weights["url_match"] / 2.0)

        text_hits = self._match_count(text_lower, terms)
        text_score = min(5.0, text_hits) * (self._weights["text_match"] / 5.0)

        canonical = (
            doc.metadata.get("canonical_url")
            if isinstance(doc.metadata, dict)
            else None
        )
        canonical_bonus = self._weights["canonical_bonus"] if canonical else 0.0
        short_penalty = self._weights["short_penalty"] if wc < _SHORT_THRESHOLD else 0.0
        empty_penalty = self._weights["empty_penalty"] if wc < _EMPTY_THRESHOLD else 0.0

        return RankingScore(
            quality=quality,
            position=pos_score,
            length=length_score,
            title_match=title_score,
            url_match=url_score,
            text_match=text_score,
            canonical_bonus=canonical_bonus,
            short_penalty=short_penalty,
            empty_penalty=empty_penalty,
        )
