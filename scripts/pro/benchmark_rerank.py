#!/usr/bin/env python3
"""Benchmark: vector-only vs hybrid vs hybrid+reranker."""

from __future__ import annotations

import json
import logging
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s %(message)s")
log = logging.getLogger("benchmark_rerank")

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "evaluation" / "corpus"


def load_queries():
    queries, rel_map = [], {}
    with open(CORPUS_DIR / "queries.jsonl") as f:  # noqa: PTH123
        for line in f:
            queries.append(json.loads(line))  # noqa: PERF401
    with open(CORPUS_DIR / "relevance.jsonl") as f:  # noqa: PTH123
        for line in f:
            d = json.loads(line)
            rel_map.setdefault(d["qid"], []).append(d)
    return queries, rel_map


def compute_metrics(retrieved, gold_set, gold_rel, k=10):
    ids = [r["doc_id"] for r in retrieved[:k]]
    rel = len(gold_set)
    r1 = len(set(ids[:1]) & gold_set) / rel if rel else 0
    r5 = len(set(ids[:5]) & gold_set) / rel if rel else 0
    r10 = len(set(ids[:10]) & gold_set) / rel if rel else 0
    p5 = len(set(ids[:5]) & gold_set) / 5
    mrr = next((1.0 / (i + 1) for i, d in enumerate(ids) if d in gold_set), 0.0)
    dcg = sum((2 ** gold_rel.get(d, 0) - 1) / math.log2(i + 2) for i, d in enumerate(ids))
    ideal = sorted(gold_rel.values(), reverse=True)
    idcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(ideal[:k]))
    ndcg = dcg / idcg if idcg else 0.0
    hits = 0
    ap_sum = 0.0
    for i, d in enumerate(ids):
        if d in gold_set:
            hits += 1
            ap_sum += hits / (i + 1)
    ap = ap_sum / rel if rel else 0.0
    return r1, r5, r10, p5, mrr, ndcg, ap


def run_config(name, retriever_fn, queries, rel_map):
    log.warning("Running: %s", name)
    all_lat, all_r1, all_r5, all_r10, all_p5, all_mrr, all_ndcg, all_ap = ([] for _ in range(8))
    total_no_ctx = 0
    for q in queries:
        gold = rel_map.get(q["qid"], [])
        gs = {r["doc_id"] for r in gold}
        gr = {r["doc_id"]: r["relevance"] for r in gold}

        start = time.monotonic()
        results = retriever_fn(q["query"])
        elapsed = (time.monotonic() - start) * 1000
        all_lat.append(elapsed)

        score = 0.0
        if results:
            for key in ("score", "rerank_score", "hybrid_score"):
                val = results[0].get(key)
                if val is not None:
                    score = val
                    break
        if not results or score < 0.6:
            total_no_ctx += 1

        m = compute_metrics(results, gs, gr)
        all_r1.append(m[0])
        all_r5.append(m[1])
        all_r10.append(m[2])
        all_p5.append(m[3])
        all_mrr.append(m[4])
        all_ndcg.append(m[5])
        all_ap.append(m[6])

    slat = sorted(all_lat)
    n = len(slat)
    return {
        "Recall@1": round(statistics.mean(all_r1), 4),
        "Recall@5": round(statistics.mean(all_r5), 4),
        "Recall@10": round(statistics.mean(all_r10), 4),
        "Precision@5": round(statistics.mean(all_p5), 4),
        "MRR": round(statistics.mean(all_mrr), 4),
        "MAP": round(statistics.mean(all_ap), 4),
        "nDCG@10": round(statistics.mean(all_ndcg), 4),
        "P50": round(slat[max(0, int(n * 0.50))], 2),
        "P95": round(slat[max(0, int(n * 0.95))], 2),
        "P99": round(slat[max(0, int(n * 0.99))], 2),
        "Throughput": round(len(queries) / (sum(all_lat) / 1000), 2),
        "No-context": round(total_no_ctx / len(queries), 4),
    }


def main() -> int:
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient
    from motor.intelligence.reranking.reranker import CrossEncoderReranker
    from motor.intelligence.retrieval.hybrid import HybridRetriever
    from motor.intelligence.retrieval.lexical import LexicalRetriever
    from motor.intelligence.retrieval.vector import VectorRetriever

    cfg = UraConfig()
    qc = QdrantClient.instancia(cfg)
    if not qc.disponible:
        log.error("Qdrant not available")
        return 1

    queries, rel_map = load_queries()
    log.warning("Loaded %d queries", len(queries))

    vec = VectorRetriever(qc)
    lex = LexicalRetriever()
    hybrid = HybridRetriever(vec, lex, alpha=0.7, beta=0.3)
    reranker = CrossEncoderReranker()

    configs = {
        "Vector only": lambda q: vec.search(q, 10),
        "Hybrid (α=0.7)": lambda q: hybrid.search(q, 10),  # noqa: RUF001
        "Hybrid+Reranker": lambda q: reranker.rerank(q, hybrid.search(q, 20)),
    }

    results = {}
    for name, fn in configs.items():
        results[name] = run_config(name, fn, queries, rel_map)

    # Print comparison
    metrics = ["Recall@10", "Precision@5", "MRR", "MAP", "nDCG@10", "P50", "P95", "P99", "Throughput", "No-context"]

    v = results["Vector only"]
    h = results["Hybrid (α=0.7)"]  # noqa: RUF001
    hr = results["Hybrid+Reranker"]

    for m in metrics:
        v[m]
        hv = h[m]
        hrv = hr[m]
        round((hrv - hv) / hv * 100, 1) if hv else 0

    # Acceptance criteria
    accept = True
    checks = [
        ("MAP ≥ Vector-only", hr["MAP"] >= v["MAP"], f"{hr['MAP']:.4f} >= {v['MAP']:.4f}"),
        ("nDCG ≥ Vector-only", hr["nDCG@10"] >= v["nDCG@10"], f"{hr['nDCG@10']:.4f} >= {v['nDCG@10']:.4f}"),
        ("Recall@10 ≥ Hybrid", hr["Recall@10"] >= h["Recall@10"], f"{hr['Recall@10']:.4f} >= {h['Recall@10']:.4f}"),
        (
            "No-context ≤ Hybrid",
            hr["No-context"] <= h["No-context"],
            f"{hr['No-context']:.2%} <= {h['No-context']:.2%}",
        ),
        ("P95 ≤ Hybrid +25%", hr["P95"] <= h["P95"] * 1.25, f"{hr['P95']:.2f} <= {h['P95'] * 1.25:.2f}"),
    ]
    for _label, passed, _detail in checks:
        if not passed:
            accept = False

    # If failed, analyze
    if not accept:
        if hr["MAP"] < v["MAP"]:
            pass
        if hr["nDCG@10"] < v["nDCG@10"]:
            pass
        if hr["Recall@10"] < h["Recall@10"]:
            pass

    return 0 if accept else 1


if __name__ == "__main__":
    sys.exit(main())
