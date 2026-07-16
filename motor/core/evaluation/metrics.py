"""Métricas de evaluación para Retrieval.

Implementa:
  - Recall@K
  - Precision@K
  - MRR (Mean Reciprocal Rank)
  - MAP (Mean Average Precision)
  - nDCG@K (Normalized Discounted Cumulative Gain)
"""

from __future__ import annotations

import math


def recall_at_k(relevant: set[str], retrieved: list[str], k: int) -> float:
    """Recall@K: proporción de ítems relevantes recuperados en top K."""
    if not relevant:
        return 0.0
    retrieved_k = retrieved[:k]
    hits = sum(1 for doc in retrieved_k if doc in relevant)
    return hits / len(relevant)


def precision_at_k(relevant: set[str], retrieved: list[str], k: int) -> float:
    """Precision@K: proporción de top K que son relevantes."""
    if k <= 0:
        return 0.0
    retrieved_k = retrieved[:k]
    if not retrieved_k:
        return 0.0
    hits = sum(1 for doc in retrieved_k if doc in relevant)
    return hits / len(retrieved_k)


def mrr(relevant: set[str], retrieved: list[str]) -> float:
    """Mean Reciprocal Rank: 1/rank del primer relevante, 0 si ninguno."""
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1.0 / rank
    return 0.0


def _average_precision(relevant: set[str], retrieved: list[str]) -> float:
    """Average Precision para una consulta."""
    if not relevant:
        return 0.0
    score = 0.0
    hits = 0
    for k, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            hits += 1
            score += precision_at_k(relevant, retrieved, k)
    return score / len(relevant) if relevant else 0.0


def map_at_k(
    queries: list[tuple[set[str], list[str]]],
    k: int,
) -> float:
    """Mean Average Precision@K sobre múltiples consultas."""
    if not queries:
        return 0.0
    total = 0.0
    for relevant, retrieved in queries:
        ap = _average_precision(relevant, retrieved[:k])
        total += ap
    return total / len(queries)


def _dcg(relevances: list[float], k: int) -> float:
    """Discounted Cumulative Gain@K."""
    dcg = 0.0
    for i, rel in enumerate(relevances[:k], start=1):
        if i == 1:
            dcg += rel
        else:
            dcg += rel / math.log2(i)
    return dcg


def ndcg_at_k(
    relevant: set[str],
    retrieved: list[str],
    k: int,
    relevance_scores: dict[str, float] | None = None,
) -> float:
    """nDCG@K: Normalized Discounted Cumulative Gain.

    relevance_scores: mapeo doc_id -> relevancia (0.0 a 1.0).
    Si no se provee, se usa 1.0 para docs relevantes, 0.0 para no relevantes.
    """
    # Relevancias observadas
    observed: list[float] = []
    for doc in retrieved[:k]:
        if relevance_scores:
            observed.append(relevance_scores.get(doc, 0.0))
        else:
            observed.append(1.0 if doc in relevant else 0.0)

    # Relevancias ideales
    ideal: list[float] = []
    if relevance_scores:
        ideal = sorted(
            (relevance_scores.get(d, 0.0) for d in relevant),
            reverse=True,
        )
    else:
        ideal = [1.0] * len(relevant)

    dcg = _dcg(observed, k)
    idcg = _dcg(ideal, k)

    if idcg <= 0:
        return 0.0
    return dcg / idcg
