"""ContextRetriever — búsqueda híbrida sobre memoria episódica."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from motor.intelligence.memory.episodic import Episode, EpisodeStore  # noqa: TC001
from motor.intelligence.memory.record import MemoryType  # noqa: TC001

log = logging.getLogger("ura.memory.retrieval")

DEFAULT_WEIGHTS: dict[str, float] = {
    "semantic": 0.0,
    "recency": 0.35,
    "importance": 0.35,
    "confidence": 0.30,
}


@dataclass
class ContextQuery:
    text: str = ""
    session_id: str | None = None
    tags: list[str] | None = None
    memory_type: MemoryType | None = None
    k: int = 10
    offset: int = 0
    weights: dict[str, float] | None = None


@dataclass
class ContextResult:
    episode: Episode
    score: float = 0.0
    semantic_score: float = 0.0
    recency_score: float = 0.0
    importance_score: float = 0.0
    confidence_score: float = 0.0
    rank: int = 0

    @property
    def explanation(self) -> str:
        parts = []
        if self.semantic_score > 0:
            parts.append(f"sem={self.semantic_score:.2f}")
        parts.append(f"rec={self.recency_score:.2f}")
        parts.append(f"imp={self.importance_score:.2f}")
        parts.append(f"con={self.confidence_score:.2f}")
        return f"score={self.score:.3f} ({', '.join(parts)})"


@dataclass
class ContextResultList:
    results: list[ContextResult] = field(default_factory=list)
    total: int = 0
    elapsed_ms: float = 0.0
    query: ContextQuery | None = None

    def __getitem__(self, index: int) -> ContextResult:
        return self.results[index]

    def __len__(self) -> int:
        return len(self.results)

    def to_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "id": r.episode.id,
                "session_id": r.episode.session_id,
                "score": r.score,
                "payload": r.episode.payload[:200] if r.episode.payload else "",
                "timestamp": r.episode.timestamp,
                "importance": r.episode.importance,
                "explanation": r.explanation,
            }
            for r in self.results
        ]


class ContextRetriever:
    def __init__(
        self,
        store: EpisodeStore,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._store = store
        self._weights = dict(weights or DEFAULT_WEIGHTS)

    def search(self, query: ContextQuery) -> ContextResultList:
        start = time.monotonic()
        weights = dict(query.weights or self._weights)
        k = max(1, query.k)
        offset = max(0, query.offset)

        candidates = self._collect_candidates(query)
        scored = self._score(candidates, query, weights)
        scored.sort(key=lambda x: x.score, reverse=True)

        total = len(scored)
        page = scored[offset : offset + k]

        elapsed = (time.monotonic() - start) * 1000
        return ContextResultList(results=page, total=total, elapsed_ms=round(elapsed, 2), query=query)

    def _collect_candidates(self, query: ContextQuery) -> list[Episode]:

        if query.session_id:
            episodes = self._store.get_by_session(query.session_id, limit=10000)
        else:
            episodes = self._store.get_recent(k=10000)

        # Filter out expired
        valid = [e for e in episodes if not self._is_expired(e)]

        # Filter by tags (any match)
        if query.tags:
            tag_set = set(query.tags)
            valid = [e for e in valid if tag_set & set(e.tags)]

        return valid

    def _is_expired(self, episode: Episode) -> bool:
        if episode.ttl <= 0:
            return False
        created = datetime.fromisoformat(episode.timestamp)
        age = (datetime.now(UTC) - created).total_seconds()
        if age > episode.ttl:
            self._store.delete(episode.id)
            return True
        return False

    def _score(
        self,
        episodes: list[Episode],
        query: ContextQuery,
        weights: dict[str, float],
    ) -> list[ContextResult]:
        now = datetime.now(UTC)
        sem_weight = weights.get("semantic", 0.0)
        rec_weight = weights.get("recency", 0.35)
        imp_weight = weights.get("importance", 0.35)
        con_weight = weights.get("confidence", 0.30)

        # Compute max importance and confidence for normalization
        max_imp = max((e.importance for e in episodes), default=1.0)
        max_con = max((e.confidence for e in episodes), default=1.0)
        max_age_seconds = self._max_age_seconds(episodes, now)

        scored: list[ContextResult] = []

        for ep in episodes:
            cr = ContextResult(episode=ep)

            # Semantic score (only if embeddings exist and query has text)
            if sem_weight > 0 and query.text and ep.embedding:
                cr.semantic_score = self._semantic_score(query.text, ep.embedding)

            # Recency score: 1.0 for newest, 0.0 for oldest
            if max_age_seconds > 0:
                age = (now - datetime.fromisoformat(ep.timestamp)).total_seconds()
                cr.recency_score = max(0.0, 1.0 - age / max_age_seconds)
            else:
                cr.recency_score = 1.0

            # Importance score (normalized)
            cr.importance_score = ep.importance / max_imp if max_imp > 0 else 0.0

            # Confidence score (normalized)
            cr.confidence_score = ep.confidence / max_con if max_con > 0 else 0.0

            # Weighted sum
            cr.score = (
                sem_weight * cr.semantic_score
                + rec_weight * cr.recency_score
                + imp_weight * cr.importance_score
                + con_weight * cr.confidence_score
            )

            scored.append(cr)

        # Assign ranks
        for i, r in enumerate(scored):
            r.rank = i

        return scored

    def _max_age_seconds(self, episodes: list[Episode], now: datetime) -> float:
        max_age = 0.0
        for ep in episodes:
            age = (now - datetime.fromisoformat(ep.timestamp)).total_seconds()
            max_age = max(max_age, age)
        return max_age

    def _semantic_score(self, query: str, embedding: list[float]) -> float:
        # NOTE: stub para integracion futura con KE 2.0
        # 1. generar embedding del query via modelo de embeddings
        # 2. cosine similarity entre query_embedding y episode.embedding
        return 0.0
