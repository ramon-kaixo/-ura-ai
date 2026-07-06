"""NoOpReranker — pasa los resultados sin modificar (fallback)."""

from __future__ import annotations

from typing import Any

from motor.intelligence.reranking.base import BaseReranker


class NoOpReranker(BaseReranker):
    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return candidates
