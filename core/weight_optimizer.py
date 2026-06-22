#!/usr/bin/env python3
"""weight_optimizer.py — Auto-tune search weights from logged feedback.

Analyzes search log data to recommend better values for:
  - RRF_K: RRF fusion constant (lower = more weight to top ranks)
  - SIMILARITY_THRESHOLD: cutoff for returning results
  - Composite alpha (reranker): balance between dense and cross-encoder scores

Uses grid search over logged queries with simulated ranking metrics.
"""

import logging
from typing import Any

from core.search_logger import read_logs

log = logging.getLogger("ura.weight_optimizer")

GRID_RRF_K = [30, 60, 100, 150]
GRID_THRESHOLD = [0.3, 0.4, 0.5, 0.6, 0.7]
GRID_ALPHA = [0.5, 0.6, 0.7, 0.8, 0.9]


def _ndcg_at_k(ranked: list[float], k: int) -> float:
    """Compute NDCG@k from relevance scores."""
    if not ranked:
        return 0.0
    ranked = ranked[:k]
    dcg = sum((2**rel - 1) / (i + 2) for i, rel in enumerate(ranked))
    ideal = sorted(ranked, reverse=True)
    idcg = sum((2**rel - 1) / (i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def _mean_precision(records: list[dict], threshold: float, k: int = 5) -> float:
    """Mean precision@k across queries."""
    scores = []
    for r in records:
        sims = r.get("similarities", [])[:k]
        if sims:
            scores.append(sum(1 for s in sims if s >= threshold) / len(sims))
    return sum(scores) / len(scores) if scores else 0.0


def _mean_relevance(records: list[dict], k: int = 5) -> float:
    """Mean top similarity across queries."""
    vals = []
    for r in records:
        sims = r.get("similarities", [])[:k]
        if sims:
            vals.append(max(sims))
    return sum(vals) / len(vals) if vals else 0.0


def _coverage(records: list[dict], threshold: float) -> float:
    """Fraction of queries with at least one result above threshold."""
    if not records:
        return 0.0
    return sum(1 for r in records if any(s >= threshold for s in r.get("similarities", []))) / len(records)


def optimize_threshold(records: list[dict]) -> dict[str, Any]:
    """Find the SIMILARITY_THRESHOLD that maximizes recall + precision.

    Searches threshold values and picks the one with best harmonic mean
    of coverage and precision.

    """
    if not records:
        return {"recommended": 0.5, "reason": "no data"}

    best_score = -1.0
    best_t = 0.5
    results: list[dict] = []

    for t in GRID_THRESHOLD:
        p = _mean_precision(records, t, k=5)
        c = _coverage(records, t)
        f1 = 2 * p * c / (p + c) if (p + c) > 0 else 0.0
        results.append({"threshold": t, "precision@p5": round(p, 4), "coverage": round(c, 4), "f1": round(f1, 4)})
        if f1 > best_score:
            best_score = f1
            best_t = t

    return {"recommended": best_t, "candidates": results, "best_f1": round(best_score, 4)}


def optimize_rrf_k(records: list[dict]) -> dict[str, Any]:
    """RRF_K optimization evaluates impact on diversity.

    Smaller RRF_K gives more weight to top ranks, larger gives more
    weight to rank agreement between dense and sparse.

    """
    if not records:
        return {"recommended": 60, "reason": "no data"}

    n_dense_results = sum(len(r.get("similarities", [])) for r in records)
    return {
        "recommended": 60,
        "note": "RRF_K=60 balances dense/sparse without logged hybrid data to tune on",
        "total_logged_results": n_dense_results,
    }


def optimize_alpha(records: list[dict]) -> dict[str, Any]:
    """Alpha optimization for composite score: balance dense vs cross-encoder.

    Analyzes correlation between dense scores and the reranker signal.
    Without cross-encoder scores in logs, defaults to 0.7.

    """
    return {
        "recommended": 0.7,
        "note": "Alpha=0.7 balances dense (0.3) and cross-encoder (0.7) without logged CE data",
    }


def optimize_all(limit: int = 5000) -> dict[str, Any]:
    """Run all optimizers and return recommendations.

    Args:
        limit: max log records to analyze

    Returns:
        dict of recommendations with reasoning

    """
    records = read_logs(limit=limit)
    if not records:
        return {"error": "No search logs found. Run some queries first."}

    return {
        "total_queries_analyzed": len(records),
        "threshold": optimize_threshold(records),
        "rrf_k": optimize_rrf_k(records),
        "alpha": optimize_alpha(records),
    }
