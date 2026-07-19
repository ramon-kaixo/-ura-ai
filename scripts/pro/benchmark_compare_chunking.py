#!/usr/bin/env python3
"""Compare KE 1.x (single-chunk) vs KE 2.0 (semantic chunking).
Runs same queries against both indices and compares metrics."""

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
log = logging.getLogger("benchmark_compare")

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "evaluation" / "corpus"
RESULTS_DIR = CORPUS_DIR.parent / "results"
KE1_COLLECTION = "ura_documents"
KE2_COLLECTION = "ura_docs_semantic"


def load_queries():
    queries = []
    relevance_map = {}
    with open(CORPUS_DIR / "queries.jsonl") as f:
        for line in f:
            d = json.loads(line)
            queries.append(d)
    with open(CORPUS_DIR / "relevance.jsonl") as f:
        for line in f:
            d = json.loads(line)
            relevance_map.setdefault(d["qid"], []).append(d)
    return queries, relevance_map


def search_collection(qc, texto, collection, limit=10):
    vector = qc.generar_embedding(texto)
    if qc._cliente:
        hits = qc._cliente.query_points(
            collection_name=collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        return hits.points if hits else []
    return []


def compute_metrics(retrieved_docs, gold_set, gold_relevance, k=10):
    retrieved_ids = [r.doc_id for r in retrieved_docs]
    rel_count = len(gold_set)
    r1 = len(set(retrieved_ids[:1]) & gold_set) / rel_count if rel_count else 0
    r5 = len(set(retrieved_ids[:5]) & gold_set) / rel_count if rel_count else 0
    r10 = len(set(retrieved_ids[:10]) & gold_set) / rel_count if rel_count else 0
    p5 = len(set(retrieved_ids[:5]) & gold_set) / 5

    mrr = 0.0
    for i, doc in enumerate(retrieved_ids):
        if doc in gold_set:
            mrr = 1.0 / (i + 1)
            break
    ndcg = 0.0
    dcg = 0.0
    for i, doc in enumerate(retrieved_ids[:k]):
        rel = gold_relevance.get(doc, 0)
        dcg += (2**rel - 1) / math.log2(i + 2)
    ideal = sorted(gold_relevance.values(), reverse=True)
    idcg = 0.0
    for i, rel in enumerate(ideal[:k]):
        idcg += (2**rel - 1) / math.log2(i + 2)
    ndcg = dcg / idcg if idcg > 0 else 0.0
    ap = 0.0
    hits = 0
    for i, doc in enumerate(retrieved_ids):
        if doc in gold_set:
            hits += 1
            ap += hits / (i + 1)
    ap = ap / rel_count if rel_count else 0.0

    return r1, r5, r10, p5, mrr, ndcg, ap


def main():
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient

    cfg = UraConfig()
    qc = QdrantClient.instancia(cfg)
    if not qc.disponible:
        log.error("Qdrant not available")
        return 1

    queries, relevance_map = load_queries()
    log.info("Loaded %d queries", len(queries))

    configs = [
        ("KE 1.x — single chunk", KE1_COLLECTION, {}),
        ("KE 2.0 — semantic chunking", KE2_COLLECTION, {}),
    ]

    all_results = {}
    for name, collection, _ in configs:
        log.info("Benchmarking %s (%s)...", name, collection)
        all_lat = []
        all_r1, all_r5, all_r10, all_p5, all_mrr, all_ndcg, all_ap = [], [], [], [], [], [], []
        total_no_ctx = 0

        for q in queries:
            gold = relevance_map.get(q["qid"], [])
            gold_set = {r["doc_id"] for r in gold}
            gold_rel = {r["doc_id"]: r["relevance"] for r in gold}

            start = time.monotonic()
            hits = search_collection(qc, q["query"], collection, limit=10)
            elapsed = (time.monotonic() - start) * 1000
            all_lat.append(elapsed)

            retrieved = []
            for h in hits:
                payload = h.payload or {}
                doc_id = payload.get("source") or payload.get("id", str(h.id))
                retrieved.append(type("obj", (), {"doc_id": doc_id, "score": h.score})())

            r1, r5, r10, p5, mrr, ndcg, ap = compute_metrics(retrieved, gold_set, gold_rel)
            all_r1.append(r1)
            all_r5.append(r5)
            all_r10.append(r10)
            all_p5.append(p5)
            all_mrr.append(mrr)
            all_ndcg.append(ndcg)
            all_ap.append(ap)

            if not retrieved or retrieved[0].score < 0.6:
                total_no_ctx += 1

        sorted_lat = sorted(all_lat)
        n = len(sorted_lat)
        results = {
            "Recall@1": round(statistics.mean(all_r1), 4),
            "Recall@5": round(statistics.mean(all_r5), 4),
            "Recall@10": round(statistics.mean(all_r10), 4),
            "Precision@5": round(statistics.mean(all_p5), 4),
            "MRR": round(statistics.mean(all_mrr), 4),
            "MAP": round(statistics.mean(all_ap), 4),
            "nDCG@10": round(statistics.mean(all_ndcg), 4),
            "Latency P50 (ms)": round(sorted_lat[max(0, int(n * 0.50))], 2),
            "Latency P95 (ms)": round(sorted_lat[max(0, int(n * 0.95))], 2),
            "Latency P99 (ms)": round(sorted_lat[max(0, int(n * 0.99))], 2),
            "Throughput (qps)": round(len(queries) / (sum(all_lat) / 1000), 2),
            "No-context rate": round(total_no_ctx / len(queries), 4),
        }
        all_results[name] = results

    # Print comparison table
    versions = list(all_results.keys())
    print(f"\n{'=' * 75}")
    print("  KE 1.x vs KE 2.0 — Chunking Comparison")
    print(f"{'=' * 75}")
    print(f"{'Metric':<22} {'KE 1.x':<12} {'KE 2.0':<12} {'Delta':<10} {'Pass?':<10}")
    print(f"{'-' * 66}")

    for metric in ["Recall@1", "Recall@5", "Recall@10", "Precision@5", "MRR", "MAP", "nDCG@10"]:
        v1 = all_results[versions[0]][metric]
        v2 = all_results[versions[1]][metric]
        delta = v2 - v1
        pct = (delta / v1 * 100) if v1 else float("inf")
        passed = pct > 0 or (v1 == 0 and v2 > 0)
        print(f"{metric:<22} {v1:<12.4f} {v2:<12.4f} {pct:>+7.1f}%  {'✅' if passed else '❌'}")

    print(f"{'-' * 66}")

    for metric in ["Latency P50 (ms)", "Latency P95 (ms)", "Latency P99 (ms)"]:
        v1 = all_results[versions[0]][metric]
        v2 = all_results[versions[1]][metric]
        delta = ((v2 - v1) / v1 * 100) if v1 else 0
        passed = delta <= 10  # P95 within baseline +10%
        print(f"{metric:<22} {v1:<12.2f} {v2:<12.2f} {delta:>+7.1f}%  {'✅' if passed else '❌'}")

    for metric in ["Throughput (qps)", "No-context rate"]:
        v1 = all_results[versions[0]][metric]
        v2 = all_results[versions[1]][metric]
        if metric == "No-context rate":
            delta = v2 - v1
            passed = delta <= 0
            print(f"{metric:<22} {v1:<12.2%} {v2:<12.2%} {delta:>+7.1%}  {'✅' if passed else '❌'}")
        else:
            delta = ((v2 - v1) / v1 * 100) if v1 else 0
            print(f"{metric:<22} {v1:<12.2f} {v2:<12.2f} {delta:>+7.1f}%")

    # Acceptance check
    r10_ke1 = all_results[versions[0]]["Recall@10"]
    r10_ke2 = all_results[versions[1]]["Recall@10"]
    p95_ke1 = all_results[versions[0]]["Latency P95 (ms)"]
    p95_ke2 = all_results[versions[1]]["Latency P95 (ms)"]
    nctx_ke1 = all_results[versions[0]]["No-context rate"]
    nctx_ke2 = all_results[versions[1]]["No-context rate"]

    accepts = []
    if r10_ke2 > r10_ke1:
        accepts.append(f"Recall@10 mejora: {r10_ke1:.4f} → {r10_ke2:.4f}")
    else:
        accepts.append(f"❌ Recall@10 NO mejora: {r10_ke1:.4f} → {r10_ke2:.4f}")

    p95_limit = p95_ke1 * 1.10
    if p95_ke2 <= p95_limit:
        accepts.append(f"P95 dentro de +10%: {p95_ke2:.2f} <= {p95_limit:.2f}")
    else:
        accepts.append(f"❌ P95 excede +10%: {p95_ke2:.2f} > {p95_limit:.2f}")

    if nctx_ke2 <= nctx_ke1:
        accepts.append(f"No-context rate no aumenta: {nctx_ke2:.2%} <= {nctx_ke1:.2%}")
    else:
        accepts.append(f"❌ No-context rate aumenta: {nctx_ke2:.2%} > {nctx_ke1:.2%}")

    print(f"\n{'=' * 75}")
    print("  Acceptance Criteria")
    print(f"{'=' * 75}")
    for a in accepts:
        print(f"  {a}")

    all_pass = all("❌" not in a for a in accepts)
    print(f"\n  {'✅ APROBADO — continuar con Retrieval Híbrido' if all_pass else '❌ RECHAZADO — revisar chunking'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
