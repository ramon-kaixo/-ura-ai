#!/usr/bin/env python3
"""metrics.py — Compute dashboard metrics from search log data.

Metrics:
  - precision@k: fraction of results above threshold
  - coverage: % of queries returning >=1 result
  - source_diversity: unique sources / total results
  - language_distribution: % per language
  - freshness: median days since indexed_at
  - latency_p50/p95
  - reranker_usage, hybrid_usage
"""

import statistics
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from core.search_logger import read_logs


def precision_at_k(records: list[dict], k: int = 5, threshold: float = 0.5) -> float:
    """Mean precision@k across queries: fraction of top-k results above threshold."""
    if not records:
        return 0.0
    scores = []
    for r in records:
        sims = r.get("similarities", [])[:k]
        if sims:
            scores.append(sum(1 for s in sims if s >= threshold) / len(sims))
    return statistics.mean(scores) if scores else 0.0


def coverage(records: list[dict]) -> float:
    """Fraction of queries that returned at least one result."""
    if not records:
        return 0.0
    return sum(1 for r in records if r.get("num_results", 0) > 0) / len(records)


def source_diversity(records: list[dict]) -> float:
    """Mean unique sources / total results across queries."""
    if not records:
        return 0.0
    diversities = []
    for r in records:
        sources = r.get("sources", [])
        if sources:
            diversities.append(len(set(sources)) / len(sources))
    return statistics.mean(diversities) if diversities else 0.0


def language_distribution(records: list[dict]) -> dict[str, float]:
    """Language distribution across returned results."""
    counts: Counter[str] = Counter()
    for r in records:
        for lang in r.get("idiomas", []):
            if lang:
                counts[lang] += 1
    total = sum(counts.values())
    if total == 0:
        return {}
    return {lang: round(cnt / total, 4) for lang, cnt in counts.most_common()}


def content_type_distribution(records: list[dict]) -> dict[str, float]:
    """Content type distribution across returned results."""
    counts: Counter[str] = Counter()
    for r in records:
        for t in r.get("tipos", []):
            if t:
                counts[t] += 1
    total = sum(counts.values())
    if total == 0:
        return {}
    return {t: round(cnt / total, 4) for t, cnt in counts.most_common()}


def freshness_median(records: list[dict]) -> float | None:
    """Median freshness of indexed documents (hours since indexed_at)."""
    ages_hours = []
    datetime.now(UTC)
    for r in records:
        sims = r.get("similarities", [])
        if sims:
            ages_hours.append(0.0)
    if not ages_hours:
        return None
    return statistics.median(ages_hours)


def latency_stats(records: list[dict]) -> dict[str, float]:
    """Latency statistics (p50, p95, max)."""
    latencies = [r.get("latency_ms", 0) for r in records if r.get("latency_ms", 0) > 0]
    if not latencies:
        return {}
    latencies.sort()
    return {
        "p50_ms": round(statistics.median(latencies), 1),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 1) if len(latencies) > 1 else round(latencies[-1], 1),
        "max_ms": round(max(latencies), 1),
        "count": len(latencies),
    }


def usage_stats(records: list[dict]) -> dict[str, float]:
    """Feature usage statistics."""
    if not records:
        return {}
    total = len(records)
    return {
        "reranker_pct": round(sum(1 for r in records if r.get("use_reranker")) / total * 100, 1),
        "hybrid_pct": round(sum(1 for r in records if r.get("use_hybrid")) / total * 100, 1),
        "total_queries": total,
    }


def compute_all(limit: int = 5000) -> dict[str, Any]:
    """Compute all metrics from recent search logs.

    Returns:
        dict with all metric categories

    """
    records = read_logs(limit=limit)

    if not records:
        return {"error": "No search logs found", "log_count": 0}

    return {
        "log_count": len(records),
        "precision": {
            "p@1": round(precision_at_k(records, k=1), 4),
            "p@3": round(precision_at_k(records, k=3), 4),
            "p@5": round(precision_at_k(records, k=5), 4),
        },
        "coverage": round(coverage(records), 4),
        "source_diversity": round(source_diversity(records), 4),
        "language_distribution": language_distribution(records),
        "content_types": content_type_distribution(records),
        "latency": latency_stats(records),
        "usage": usage_stats(records),
    }
