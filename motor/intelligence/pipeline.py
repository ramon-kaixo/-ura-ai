"""Pipeline de retrieval unificado con reranker configurable mediante feature flag."""

from __future__ import annotations

import logging
from typing import Any

from motor.intelligence.retrieval.hybrid import HybridRetriever
from motor.intelligence.retrieval.lexical import LexicalRetriever
from motor.intelligence.retrieval.vector import VectorRetriever

log = logging.getLogger("ura.pipeline.retrieval")

_RERANKER_ENABLED = False
_RERANKER_INSTANCE: Any = None


def enable_reranker(reranker: Any) -> None:
    global _RERANKER_ENABLED, _RERANKER_INSTANCE
    _RERANKER_ENABLED = True
    _RERANKER_INSTANCE = reranker
    log.info("Reranker enabled: %s", type(reranker).__name__)


def disable_reranker() -> None:
    global _RERANKER_ENABLED, _RERANKER_INSTANCE
    _RERANKER_ENABLED = False
    _RERANKER_INSTANCE = None
    log.info("Reranker disabled")


def reranker_enabled() -> bool:
    return _RERANKER_ENABLED and _RERANKER_INSTANCE is not None


def create_retrieval_pipeline(
    vector_retriever: VectorRetriever | None = None,
    lexical_retriever: LexicalRetriever | None = None,
    alpha: float = 0.7,
    beta: float = 0.3,
) -> HybridRetriever:
    vec = vector_retriever or VectorRetriever(None)  # will fail gracefully if no qdrant
    lex = lexical_retriever or LexicalRetriever()
    return HybridRetriever(vec, lex, alpha=alpha, beta=beta)


def search_with_reranker(
    query: str,
    hybrid: HybridRetriever,
    k: int = 10,
) -> list[dict[str, Any]]:
    results = hybrid.search(query, k=k)
    if reranker_enabled():
        try:
            results = _RERANKER_INSTANCE.rerank(query, results)
        except Exception as exc:
            log.warning("Reranker failed, using raw hybrid results: %s", exc)
    return results
