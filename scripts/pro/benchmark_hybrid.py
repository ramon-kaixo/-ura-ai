#!/usr/bin/env python3
"""Benchmark: vectorial vs BM25 vs hybrid vs semantic chunking baseline."""

from __future__ import annotations

import json
import logging
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
log = logging.getLogger("benchmark_hybrid")

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "evaluation" / "corpus"


def load_queries():
    queries, relevance_map = [], {}
    with open(CORPUS_DIR / "queries.jsonl") as f:
        for line in f:
            d = json.loads(line)
            queries.append(d)
    with open(CORPUS_DIR / "relevance.jsonl") as f:
        for line in f:
            d = json.loads(line)
            relevance_map.setdefault(d["qid"], []).append(d)
    return queries, relevance_map


CHUNKING_BASELINE = {
    "Recall@1": 0.1250,
    "Recall@5": 0.4567,
    "Recall@10": 0.6700,
    "Precision@5": 0.4750,
    "MRR": 0.7595,
    "MAP": 0.9423,
    "nDCG@10": 0.8346,
    "Latency P50 (ms)": 90.99,
    "Latency P95 (ms)": 195.57,
    "Latency P99 (ms)": 368.46,
    "Throughput (qps)": 9.82,
    "No-context rate": 0.215,
}


def compute_metrics(retrieved, gold_set, gold_relevance, k=10):
    ids = [r["doc_id"] for r in retrieved]
    rel = len(gold_set)
    r1 = len(set(ids[:1]) & gold_set) / rel if rel else 0
    r5 = len(set(ids[:5]) & gold_set) / rel if rel else 0
    r10 = len(set(ids[:10]) & gold_set) / rel if rel else 0
    p5 = len(set(ids[:5]) & gold_set) / 5
    mrr = next((1.0 / (i + 1) for i, d in enumerate(ids) if d in gold_set), 0.0)
    dcg = sum((2 ** gold_relevance.get(d, 0) - 1) / math.log2(i + 2) for i, d in enumerate(ids[:k]))
    ideal = sorted(gold_relevance.values(), reverse=True)
    idcg_val = sum((2**rel_v - 1) / math.log2(i + 2) for i, rel_v in enumerate(ideal[:k]))
    ndcg = dcg / idcg_val if idcg_val > 0 else 0.0
    hits = 0
    ap_sum = 0.0
    for i, d in enumerate(ids):
        if d in gold_set:
            hits += 1
            ap_sum += hits / (i + 1)
    ap = ap_sum / rel if rel else 0.0
    return r1, r5, r10, p5, mrr, ndcg, ap


def run_config(name, retriever, queries, relevance_map):
    log.info("Running: %s", name)
    all_lat, all_r1, all_r5, all_r10, all_p5, all_mrr, all_ndcg, all_ap = ([] for _ in range(8))
    total_no_ctx = 0
    for q in queries:
        gold = relevance_map.get(q["qid"], [])
        gold_set = {r["doc_id"] for r in gold}
        gold_rel = {r["doc_id"]: r["relevance"] for r in gold}

        start = time.monotonic()
        results = retriever.search(q["query"], k=10)
        elapsed = (time.monotonic() - start) * 1000
        all_lat.append(elapsed)

        score = 0.0
        if results:
            if "hibrid" in name.lower().replace("í", "i").replace("ó", "o"):
                score = results[0].get("hybrid_score", results[0].get("score", 0))
            else:
                score = results[0].get("score", 0)
        if not results or score < 0.6:
            total_no_ctx += 1

        m = compute_metrics(results, gold_set, gold_rel)
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
        "Latency P50 (ms)": round(slat[max(0, int(n * 0.50))], 2),
        "Latency P95 (ms)": round(slat[max(0, int(n * 0.95))], 2),
        "Latency P99 (ms)": round(slat[max(0, int(n * 0.99))], 2),
        "Throughput (qps)": round(len(queries) / (sum(all_lat) / 1000), 2),
        "No-context rate": round(total_no_ctx / len(queries), 4),
    }


def print_comp(name, results, baseline, metrics):
    print(f"\n{'=' * 70}")
    print(f"  {name}")
    print(f"{'=' * 70}")
    print(f"{'Metric':<22} {'Actual':<12} {'Baseline':<12} {'Delta':<10} {'Pass?':<10}")
    print(f"{'-' * 66}")
    for metric in metrics:
        v = results[metric]
        b = baseline.get(metric)
        if b and b != 0:
            delta = (v - b) / b * 100
        elif b == 0 and v > 0:
            delta = float("inf")
        else:
            delta = 0.0
        if metric.startswith("Latency"):
            passed = delta <= 15 if "P95" in metric else delta <= 20
        elif metric == "No-context rate":
            passed = v <= b
        else:
            passed = v >= b
        print(f"{metric:<22} {v:<12.4f} {(b if b else 0):<12.4f} {delta:>+7.1f}%  {'✅' if passed else '❌'}")


def main():
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient
    from motor.intelligence.retrieval.lexical import LexicalRetriever
    from motor.intelligence.retrieval.vector import VectorRetriever
    from motor.intelligence.retrieval.hybrid import HybridRetriever

    cfg = UraConfig()
    qc = QdrantClient.instancia(cfg)
    if not qc.disponible:
        log.error("Qdrant not available")
        return 1

    queries, relevance_map = load_queries()
    log.info("Loaded %d queries", len(queries))

    configs = [
        ("Vectorial puro (Qdrant)", VectorRetriever(qc)),
        ("BM25 puro", LexicalRetriever()),
    ]

    metrics = [
        "Recall@1",
        "Recall@5",
        "Recall@10",
        "Precision@5",
        "MRR",
        "MAP",
        "nDCG@10",
        "Latency P50 (ms)",
        "Latency P95 (ms)",
        "Latency P99 (ms)",
        "Throughput (qps)",
        "No-context rate",
    ]

    # First run pure configs to get their retrievers for hybrid
    all_results = {}
    for name, retriever in configs:
        all_results[name] = run_config(name, retriever, queries, relevance_map)
        print_comp(name, all_results[name], CHUNKING_BASELINE, metrics)

    # Try multiple alpha/beta combinations for hybrid
    for alpha, beta in [(0.7, 0.3), (0.5, 0.5), (0.3, 0.7)]:
        vec = VectorRetriever(qc)
        lex = LexicalRetriever()
        hybrid = HybridRetriever(vec, lex, alpha=alpha, beta=beta)
        name = f"Híbrido α={alpha} β={beta}"
        all_results[name] = run_config(name, hybrid, queries, relevance_map)
        print_comp(name, all_results[name], CHUNKING_BASELINE, metrics)

    # Acceptance: hybrid must beat chunking baseline
    best_hybrid = max(
        (r for n, r in all_results.items() if "Híbrido" in n),
        key=lambda r: r["Recall@10"],
    )
    accept = True
    print(f"\n{'=' * 70}")
    print(f"  Acceptance Criteria (vs semantic chunking baseline)")
    print(f"{'=' * 70}")

    checks = [
        (
            "Recall@10 ≥ baseline",
            best_hybrid["Recall@10"] >= CHUNKING_BASELINE["Recall@10"],
            f"{best_hybrid['Recall@10']:.4f} >= {CHUNKING_BASELINE['Recall@10']:.4f}",
        ),
        (
            "MRR ≥ baseline",
            best_hybrid["MRR"] >= CHUNKING_BASELINE["MRR"],
            f"{best_hybrid['MRR']:.4f} >= {CHUNKING_BASELINE['MRR']:.4f}",
        ),
        (
            "MAP ≥ baseline",
            best_hybrid["MAP"] >= CHUNKING_BASELINE["MAP"],
            f"{best_hybrid['MAP']:.4f} >= {CHUNKING_BASELINE['MAP']:.4f}",
        ),
        (
            "nDCG@10 ≥ baseline",
            best_hybrid["nDCG@10"] >= CHUNKING_BASELINE["nDCG@10"],
            f"{best_hybrid['nDCG@10']:.4f} >= {CHUNKING_BASELINE['nDCG@10']:.4f}",
        ),
        (
            "P95 ≤ chunking +15%",
            best_hybrid["Latency P95 (ms)"] <= CHUNKING_BASELINE["Latency P95 (ms)"] * 1.15,
            f"{best_hybrid['Latency P95 (ms)']:.2f} <= {CHUNKING_BASELINE['Latency P95 (ms)'] * 1.15:.2f}",
        ),
        (
            "No-context ≤ baseline",
            best_hybrid["No-context rate"] <= CHUNKING_BASELINE["No-context rate"],
            f"{best_hybrid['No-context rate']:.2%} <= {CHUNKING_BASELINE['No-context rate']:.2%}",
        ),
    ]
    for label, passed, detail in checks:
        print(f"  {'✅' if passed else '❌'} {label}: {detail}")
        if not passed:
            accept = False

    print(f"\n  {'✅ APROBADO — continuar con Reranking' if accept else '❌ RECHAZADO'}")
    return 0 if accept else 1


if __name__ == "__main__":
    sys.exit(main())
