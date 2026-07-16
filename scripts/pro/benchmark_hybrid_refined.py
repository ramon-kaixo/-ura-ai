#!/usr/bin/env python3
"""Hybrid retrieval refinement: compare 5 fusion strategies to meet ADR-012-01."""

from __future__ import annotations

import json
import logging
import math
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
log = logging.getLogger("benchmark_hybrid_refined")

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "evaluation" / "corpus"

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


def load_queries():
    queries, relevance_map = [], {}
    with open(CORPUS_DIR / "queries.jsonl") as f:
        for line in f:
            queries.append(json.loads(line))
    with open(CORPUS_DIR / "relevance.jsonl") as f:
        for line in f:
            d = json.loads(line)
            relevance_map.setdefault(d["qid"], []).append(d)
    return queries, relevance_map


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
    idcg_val = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(ideal[:k]))
    ndcg = dcg / idcg_val if idcg_val > 0 else 0.0
    hits = 0
    ap_sum = 0.0
    for i, d in enumerate(ids):
        if d in gold_set:
            hits += 1
            ap_sum += hits / (i + 1)
    ap = ap_sum / rel if rel else 0.0
    return r1, r5, r10, p5, mrr, ndcg, ap


# ── Fusion strategies ────────────────────────────────────────────────────────


def strategy_score_fusion(vec, lex, alpha=0.7, beta=0.3):
    """Weighted score fusion (current implementation)."""
    vr = vec.search(q := globals().get("_query", ""), k=10)
    lr = lex.search(q, k=10)
    return _fuse_weighted(vr, lr, alpha, beta)


def strategy_rrf(vec, lex, k_rrf=60):
    """Reciprocal Rank Fusion: score = sum(1/(k + rank))."""
    vr = vec.search(globals().get("_query", ""), k=10)
    lr = lex.search(globals().get("_query", ""), k=10)
    score_map: dict[str, dict] = {}
    for r in vr:
        score_map.setdefault(r["doc_id"], {"vector_rank": 999, "lexical_rank": 999})
        score_map[r["doc_id"]]["vector_rank"] = r["rank"]
    for r in lr:
        score_map.setdefault(r["doc_id"], {"vector_rank": 999, "lexical_rank": 999})
        score_map[r["doc_id"]]["lexical_rank"] = r["rank"]
    for doc_id, entry in score_map.items():
        entry["rrf"] = (1 / (k_rrf + entry["vector_rank"])) + (1 / (k_rrf + entry["lexical_rank"]))
        entry["doc_id"] = doc_id
    fused = sorted(score_map.values(), key=lambda x: x["rrf"], reverse=True)[:10]
    for i, e in enumerate(fused):
        e["rank"] = i
        e["hybrid_score"] = e["rrf"]
    return fused


def strategy_weighted_rrf(vec, lex, k_vec=60, k_lex=100):
    """Weighted RRF: different k per retriever (lower k = higher weight)."""
    vr = vec.search(globals().get("_query", ""), k=10)
    lr = lex.search(globals().get("_query", ""), k=10)
    score_map: dict[str, dict] = {}
    for r in vr:
        score_map.setdefault(r["doc_id"], {"vector_rank": 999, "lexical_rank": 999})
        score_map[r["doc_id"]]["vector_rank"] = r["rank"]
    for r in lr:
        score_map.setdefault(r["doc_id"], {"vector_rank": 999, "lexical_rank": 999})
        score_map[r["doc_id"]]["lexical_rank"] = r["rank"]
    for doc_id, entry in score_map.items():
        entry["rrf"] = (1 / (k_vec + entry["vector_rank"])) + (1 / (k_lex + entry["lexical_rank"]))
        entry["doc_id"] = doc_id
    fused = sorted(score_map.values(), key=lambda x: x["rrf"], reverse=True)[:10]
    for i, e in enumerate(fused):
        e["rank"] = i
        e["hybrid_score"] = e["rrf"]
    return fused


def strategy_dynamic(vec, lex, threshold=0.8, alpha=0.7, beta=0.3):
    """BM25 only when vector's top score < threshold."""
    vr = vec.search(globals().get("_query", ""), k=10)
    top_score = vr[0]["score"] if vr else 0
    if top_score >= threshold:
        for r in vr:
            r["hybrid_score"] = r["score"]
            r["rank"] = r["rank"]
        return vr
    lr = lex.search(globals().get("_query", ""), k=10)
    return _fuse_weighted(vr, lr, alpha, beta)


def strategy_parallel(vec, lex, alpha=0.7, beta=0.3):
    """Run both retrievers in parallel via threads."""
    q = globals().get("_query", "")
    with ThreadPoolExecutor(max_workers=2) as exe:
        vf = exe.submit(vec.search, q, 10)
        lf = exe.submit(lex.search, q, 10)
        vr = vf.result()
        lr = lf.result()
    return _fuse_weighted(vr, lr, alpha, beta)


def _fuse_weighted(vr, lr, alpha, beta):
    score_map: dict[str, dict] = {}
    v_max = max((r["score"] for r in vr), default=1.0)
    for r in vr:
        n = r["score"] / v_max if v_max > 0 else 0
        score_map.setdefault(
            r["doc_id"],
            {"doc_id": r["doc_id"], "vector_score": 0.0, "lexical_score": 0.0, "vector_rank": 999, "lexical_rank": 999},
        )
        score_map[r["doc_id"]]["vector_score"] = n
        score_map[r["doc_id"]]["vector_rank"] = r["rank"]
    l_max = max((r["score"] for r in lr), default=1.0)
    for r in lr:
        n = r["score"] / l_max if l_max > 0 else 0
        score_map.setdefault(
            r["doc_id"],
            {"doc_id": r["doc_id"], "vector_score": 0.0, "lexical_score": 0.0, "vector_rank": 999, "lexical_rank": 999},
        )
        score_map[r["doc_id"]]["lexical_score"] = n
        score_map[r["doc_id"]]["lexical_rank"] = r["rank"]
    for entry in score_map.values():
        entry["hybrid_score"] = alpha * entry["vector_score"] + beta * entry["lexical_score"]
    fused = sorted(score_map.values(), key=lambda x: x["hybrid_score"], reverse=True)[:10]
    for i, e in enumerate(fused):
        e["rank"] = i
    return fused


STRATEGIES = {
    "RRF (k=60)": lambda v, l: strategy_rrf(v, l, 60),
    "RRF (k=20)": lambda v, l: strategy_rrf(v, l, 20),
    "RRF (k=100)": lambda v, l: strategy_rrf(v, l, 100),
    "Weighted RRF (k_v=60,k_l=120)": lambda v, l: strategy_weighted_rrf(v, l, 60, 120),
    "Weighted RRF (k_v=40,k_l=100)": lambda v, l: strategy_weighted_rrf(v, l, 40, 100),
    "Score α=0.7 β=0.3": lambda v, l: strategy_score_fusion(v, l, 0.7, 0.3),
    "Score α=0.8 β=0.2": lambda v, l: strategy_score_fusion(v, l, 0.8, 0.2),
    "Score α=0.9 β=0.1": lambda v, l: strategy_score_fusion(v, l, 0.9, 0.1),
    "Dynamic (θ=0.75,α=0.7)": lambda v, l: strategy_dynamic(v, l, 0.75, 0.7, 0.3),
    "Dynamic (θ=0.80,α=0.8)": lambda v, l: strategy_dynamic(v, l, 0.80, 0.8, 0.2),
    "Dynamic (θ=0.85,α=0.9)": lambda v, l: strategy_dynamic(v, l, 0.85, 0.9, 0.1),
    "Parallel (α=0.7)": lambda v, l: strategy_parallel(v, l, 0.7, 0.3),
    "Parallel (α=0.8)": lambda v, l: strategy_parallel(v, l, 0.8, 0.2),
}


def main():
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient
    from motor.intelligence.retrieval.lexical import LexicalRetriever
    from motor.intelligence.retrieval.vector import VectorRetriever

    cfg = UraConfig()
    qc = QdrantClient.instancia(cfg)
    if not qc.disponible:
        log.error("Qdrant not available")
        return 1

    queries, relevance_map = load_queries()
    log.info("Loaded %d queries", len(queries))

    # Pre-build retrievers
    vec = VectorRetriever(qc)
    lex = LexicalRetriever()

    results: dict[str, dict] = {}
    for name, strategy_fn in STRATEGIES.items():
        log.warning("Running: %s", name)
        all_lat, all_r1, all_r5, all_r10, all_p5, all_mrr, all_ndcg, all_ap = ([] for _ in range(8))
        total_no_ctx = 0
        exclusive_lexical, exclusive_vector = 0, 0

        for q in queries:
            gold = relevance_map.get(q["qid"], [])
            gold_set = {r["doc_id"] for r in gold}
            gold_rel = {r["doc_id"]: r["relevance"] for r in gold}
            globals()["_query"] = q["query"]

            start = time.monotonic()
            r = strategy_fn(vec, lex)
            elapsed = (time.monotonic() - start) * 1000
            all_lat.append(elapsed)

            score = r[0].get("hybrid_score", r[0].get("score", 0)) if r else 0
            if not r or score < 0.6:
                total_no_ctx += 1

            # Track exclusive contributions
            vr = vec.search(q["query"], k=10)
            lr = lex.search(q["query"], k=10)
            v_ids = {x["doc_id"] for x in vr}
            l_ids = {x["doc_id"] for x in lr}
            r_ids = {x["doc_id"] for x in r}
            if l_ids - v_ids:
                exclusive_lexical += 1
            if v_ids - l_ids:
                exclusive_vector += 1

            m = compute_metrics(r, gold_set, gold_rel)
            all_r1.append(m[0])
            all_r5.append(m[1])
            all_r10.append(m[2])
            all_p5.append(m[3])
            all_mrr.append(m[4])
            all_ndcg.append(m[5])
            all_ap.append(m[6])

        slat = sorted(all_lat)
        n = len(slat)
        results[name] = {
            "Recall@1": round(statistics.mean(all_r1), 4),
            "Recall@5": round(statistics.mean(all_r5), 4),
            "Recall@10": round(statistics.mean(all_r10), 4),
            "Precision@5": round(statistics.mean(all_p5), 4),
            "MRR": round(statistics.mean(all_mrr), 4),
            "MAP": round(statistics.mean(all_ap), 4),
            "nDCG@10": round(statistics.mean(all_ndcg), 4),
            "P50": round(slat[max(0, int(n * 0.50))], 2),
            "P95": round(slat[max(0, int(n * 0.95))], 2),
            "Throughput": round(len(queries) / (sum(all_lat) / 1000), 2),
            "No-context": round(total_no_ctx / len(queries), 4),
        }

    # Print comparison table
    metrics = ["Recall@10", "MRR", "MAP", "nDCG@10", "P50", "P95", "Throughput", "No-context"]
    print(f"\n{'=' * 120}")
    print(
        f"  {'Strategy':<32} {'R@10':<8} {'MRR':<8} {'MAP':<8} {'nDCG':<8} {'P50':<8} {'P95':<8} {'TPS':<8} {'NoCtx':<8} {'Pass':<6}"
    )
    print(f"{'=' * 120}")

    def passes(name, r):
        b = CHUNKING_BASELINE
        return (
            r["Recall@10"] >= b["Recall@10"]
            and r["MAP"] >= b["MAP"]
            and r["nDCG@10"] >= b["nDCG@10"]
            and r["P95"] <= b["Latency P95 (ms)"] * 1.15
        )

    best = None
    best_score = -1
    for name, r in sorted(results.items()):
        p = passes(name, r)
        flag = "✅" if p else "❌"
        print(
            f"  {name:<32} {r['Recall@10']:<8.4f} {r['MRR']:<8.4f} {r['MAP']:<8.4f} {r['nDCG@10']:<8.4f} {r['P50']:<8.2f} {r['P95']:<8.2f} {r['Throughput']:<8.2f} {r['No-context']:<8.2%} {flag:<6}"
        )
        if p:
            # Objective: maximize R@10 + MAP + nDCG, penalize P95 > baseline
            obj = r["Recall@10"] + r["MAP"] + r["nDCG@10"]
            obj -= max(0, (r["P95"] - CHUNKING_BASELINE["Latency P95 (ms)"]) / 1000)
            if obj > best_score:
                best_score = obj
                best = name

    print(f"\n{'=' * 60}")
    if best:
        print(f"  🏆 Best strategy: {best}")
        print(f"  Objective score: {best_score:.4f}")
    else:
        print(f"  ❌ No strategy passes all criteria")
        # Show closest
        best_all = max(
            results.keys(), key=lambda n: results[n]["Recall@10"] + results[n]["MAP"] + results[n]["nDCG@10"]
        )
        print(f"  Closest: {best_all}")

    print(
        f"\n  {'✅ APROBADO — continuar con Reranking' if best else '❌ Ninguna estrategia supera todos los criterios'}"
    )
    return 0 if best else 1


if __name__ == "__main__":
    sys.exit(main())
