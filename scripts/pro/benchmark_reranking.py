#!/usr/bin/env python3
"""Benchmark: Vector-only vs Hybrid vs Hybrid+Reranker (NoOp, LLM)."""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
log = logging.getLogger("benchmark_rerank")

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "evaluation" / "corpus"

VECTOR_BASELINE = {
    "Recall@10": 0.6700,
    "MRR": 0.7595,
    "MAP": 0.9423,
    "nDCG@10": 0.8346,
    "P95": 195.57,
    "No-context rate": 0.215,
}
HYBRID_BASELINE = {
    "Recall@10": 0.8708,
    "MRR": 0.7938,
    "MAP": 0.6444,
    "nDCG@10": 0.6498,
    "P95": 200.27,
    "No-context rate": 0.005,
}


def load_queries():
    queries, rel = [], {}
    with open(CORPUS_DIR / "queries.jsonl") as f:
        for l in f:
            queries.append(json.loads(l))
    with open(CORPUS_DIR / "relevance.jsonl") as f:
        for l in f:
            d = json.loads(l)
            rel.setdefault(d["qid"], []).append(d)
    return queries, rel


def compute(retrieved, gold_set, gold_rel, k=10):
    ids = [r["doc_id"] for r in retrieved[:k]]
    rel = len(gold_set)
    r10 = len(set(ids[:10]) & gold_set) / rel if rel else 0
    p5 = len(set(ids[:5]) & gold_set) / 5
    mrr = next((1.0 / (i + 1) for i, d in enumerate(ids) if d in gold_set), 0.0)
    dcg = sum((2 ** gold_rel.get(d, 0) - 1) / math.log2(i + 2) for i, d in enumerate(ids))
    ideal = sorted(gold_rel.values(), reverse=True)
    idcg_val = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(ideal[:k]))
    ndcg = dcg / idcg_val if idcg_val > 0 else 0.0
    hits, ap_sum = 0, 0.0
    for i, d in enumerate(ids):
        if d in gold_set:
            hits += 1
            ap_sum += hits / (i + 1)
    ap = ap_sum / rel if rel else 0.0
    return r10, p5, mrr, ndcg, ap


def run(name, retriever_fn, queries, rel_map, reranker=None):
    all_r10, all_p5, all_mrr, all_ndcg, all_ap = ([] for _ in range(5))
    all_lat, no_ctx = [], 0
    for q in queries:
        gold = rel_map.get(q["qid"], [])
        gs = {r["doc_id"] for r in gold}
        gr = {r["doc_id"]: r["relevance"] for r in gold}

        start = time.monotonic()
        results = retriever_fn(q["query"], k=10)
        if reranker:
            results = reranker.rerank(q["query"], results)
        elapsed = (time.monotonic() - start) * 1000
        all_lat.append(elapsed)

        score = results[0].get("reranker_score", results[0].get("score", 0)) if results else 0
        if not results or score < 0.6:
            no_ctx += 1

        m = compute(results, gs, gr)
        all_r10.append(m[0])
        all_p5.append(m[1])
        all_mrr.append(m[2])
        all_ndcg.append(m[3])
        all_ap.append(m[4])

    slat = sorted(all_lat)
    n = len(slat)
    return {
        "Recall@10": round(statistics.mean(all_r10), 4),
        "Precision@5": round(statistics.mean(all_p5), 4),
        "MRR": round(statistics.mean(all_mrr), 4),
        "MAP": round(statistics.mean(all_ap), 4),
        "nDCG@10": round(statistics.mean(all_ndcg), 4),
        "P50": round(slat[max(0, int(n * 0.50))], 2),
        "P95": round(slat[max(0, int(n * 0.95))], 2),
        "P99": round(slat[max(0, int(n * 0.99))], 2),
        "Throughput": round(len(queries) / (sum(all_lat) / 1000), 2),
        "No-context": round(no_ctx / len(queries), 4),
    }


def main():
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient
    from motor.intelligence.reranking.llm import LLMReranker
    from motor.intelligence.reranking.noop import NoOpReranker
    from motor.intelligence.retrieval.hybrid import HybridRetriever
    from motor.intelligence.retrieval.lexical import LexicalRetriever
    from motor.intelligence.retrieval.vector import VectorRetriever

    cfg = UraConfig()
    qc = QdrantClient.instancia(cfg)
    if not qc.disponible:
        log.error("Qdrant not available")
        return 1

    queries, rel_map = load_queries()
    log.info("Loaded %d queries", len(queries))

    vec = VectorRetriever(qc)
    lex = LexicalRetriever()
    hybrid = HybridRetriever(vec, lex, alpha=0.7, beta=0.3)

    configs = {
        "Vector only": vec.search,
        "Hybrid (NoOp reranker)": hybrid.search,
    }

    all_results = {}
    for name, fn in configs.items():
        all_results[name] = run(name, fn, queries, rel_map)

    # Hybrid + NoOpReranker
    all_results["Hybrid + NoOp"] = run(
        "Hybrid+NoOp", hybrid.search, queries, rel_map, reranker=NoOpReranker()
    )

    # Hybrid + LLMReranker (only first 50 queries due to time)
    log.warning("LLMReranker: ejecutando primeras 50 queries (costoso)...")
    small_queries = queries[:50]
    small_rel = {k: v for k, v in rel_map.items() if any(q["qid"] == k for q in small_queries)}
    llm = LLMReranker(top_k=5)
    all_results["Hybrid + LLM"] = run(
        "Hybrid+LLM",
        hybrid.search,
        small_queries,
        small_rel,
        reranker=llm,
    )

    print(f"\n{'=' * 100}")
    print(
        f"  {'Config':<25} {'R@10':<8} {'P@5':<8} {'MRR':<8} {'MAP':<8} {'nDCG':<8} {'P50':<8} {'P95':<8} {'P99':<8} {'TPS':<8} {'NoCtx':<8}"
    )
    print(f"{'=' * 100}")
    for name in ["Vector only", "Hybrid (NoOp reranker)", "Hybrid + NoOp", "Hybrid + LLM"]:
        r = all_results.get(name)
        if r is None:
            continue
        print(
            f"  {name:<25} {r['Recall@10']:<8.4f} {r['Precision@5']:<8.4f} {r['MRR']:<8.4f} {r['MAP']:<8.4f} {r['nDCG@10']:<8.4f} {r['P50']:<8.2f} {r['P95']:<8.2f} {r['P99']:<8.2f} {r['Throughput']:<8.2f} {r['No-context']:<8.2%}"
        )

    # Acceptance for Hybrid+Reranker vs criteria
    print(f"\n{'=' * 100}")
    print("  Acceptance Criteria (Hybrid + Reranker)")
    print(f"{'=' * 100}")

    for reranker_name in ["Hybrid + NoOp", "Hybrid + LLM"]:
        r = all_results.get(reranker_name)
        if r is None:
            continue
        print(f"\n  {reranker_name}:")
        checks = [
            (
                "MAP >= Vector-only",
                r["MAP"] >= VECTOR_BASELINE["MAP"],
                f"{r['MAP']:.4f} >= {VECTOR_BASELINE['MAP']:.4f}",
            ),
            (
                "nDCG >= Vector-only",
                r["nDCG@10"] >= VECTOR_BASELINE["nDCG@10"],
                f"{r['nDCG@10']:.4f} >= {VECTOR_BASELINE['nDCG@10']:.4f}",
            ),
            (
                "R@10 >= Hybrid",
                r["Recall@10"] >= HYBRID_BASELINE["Recall@10"],
                f"{r['Recall@10']:.4f} >= {HYBRID_BASELINE['Recall@10']:.4f}",
            ),
            (
                "No-context <= Hybrid",
                r["No-context"] <= HYBRID_BASELINE["No-context rate"],
                f"{r['No-context']:.2%} <= {HYBRID_BASELINE['No-context rate']:.2%}",
            ),
            (
                "P95 <= Hybrid +25%",
                r["P95"] <= HYBRID_BASELINE["P95"] * 1.25,
                f"{r['P95']:.2f} <= {HYBRID_BASELINE['P95'] * 1.25:.2f}",
            ),
        ]
        all_pass = True
        for label, passed, detail in checks:
            print(f"    {'✅' if passed else '❌'} {label}: {detail}")
            if not passed:
                all_pass = False
        print(f"    {'✅ APROBADO' if all_pass else '❌ RECHAZADO'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
