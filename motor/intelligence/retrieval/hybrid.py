"""HybridRetriever — fusión ponderada de scores vectoriales + léxicos."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("ura.retrieval.hybrid")

DEFAULT_ALPHA = 0.5
DEFAULT_BETA = 0.5


class HybridRetriever:
    def __init__(
        self,
        vector_retriever: Any,
        lexical_retriever: Any,
        alpha: float = DEFAULT_ALPHA,
        beta: float = DEFAULT_BETA,
    ) -> None:
        self._vector = vector_retriever
        self._lexical = lexical_retriever
        self._alpha = alpha
        self._beta = beta

    def search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        vector_results = self._vector.search(query, k=k)
        lexical_results = self._lexical.search(query, k=k)
        return self._fuse(vector_results, lexical_results, k)

    def _fuse(
        self,
        vector_results: list[dict[str, Any]],
        lexical_results: list[dict[str, Any]],
        k: int,
    ) -> list[dict[str, Any]]:
        score_map: dict[str, dict[str, Any]] = {}

        # Normalize vector scores to [0, 1]
        v_max = max((r["score"] for r in vector_results), default=1.0)
        for r in vector_results:
            doc_id = r["doc_id"]
            norm = r["score"] / v_max if v_max > 0 else 0
            entry = score_map.setdefault(
                doc_id,
                {
                    "doc_id": doc_id,
                    "vector_score": 0.0,
                    "lexical_score": 0.0,
                    "vector_rank": 999,
                    "lexical_rank": 999,
                },
            )
            entry["vector_score"] = norm
            entry["vector_rank"] = r["rank"]

        # Normalize lexical scores to [0, 1]
        l_max = max((r["score"] for r in lexical_results), default=1.0)
        for r in lexical_results:
            doc_id = r["doc_id"]
            norm = r["score"] / l_max if l_max > 0 else 0
            entry = score_map.setdefault(
                doc_id,
                {
                    "doc_id": doc_id,
                    "vector_score": 0.0,
                    "lexical_score": 0.0,
                    "vector_rank": 999,
                    "lexical_rank": 999,
                },
            )
            entry["lexical_score"] = norm
            entry["lexical_rank"] = r["rank"]

        # Compute hybrid scores
        for entry in score_map.values():
            entry["hybrid_score"] = self._alpha * entry["vector_score"] + self._beta * entry["lexical_score"]
            entry["source"] = "hybrid"

        # Sort by hybrid score descending
        fused = sorted(score_map.values(), key=lambda x: x["hybrid_score"], reverse=True)[:k]

        for rank, entry in enumerate(fused):
            entry["rank"] = rank

        return fused
