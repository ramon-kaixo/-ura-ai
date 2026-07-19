#!/usr/bin/env python3
"""Benchmark final: Vector-only vs Hybrid vs Hybrid+CrossEncoder vs Hybrid+LLM."""

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

CORPUS = Path(__file__).resolve().parent.parent.parent / "knowledge" / "evaluation" / "corpus"


def load():
    qs, rm = [], {}
    with open(CORPUS / "queries.jsonl") as f:  # noqa: PTH123
        for l in f:
            qs.append(json.loads(l))  # noqa: PERF401
    with open(CORPUS / "relevance.jsonl") as f:  # noqa: PTH123
        for l in f:
            d = json.loads(l)
            rm.setdefault(d["qid"], []).append(d)
    return qs, rm


def metrics(retrieved, gold_set, gold_rel):
    ids = [r["doc_id"] for r in retrieved[:10]]
    r = len(gold_set)
    r10 = len(set(ids) & gold_set) / r if r else 0
    p5 = len(set(ids[:5]) & gold_set) / 5
    mrr = next((1.0 / (i + 1) for i, d in enumerate(ids) if d in gold_set), 0.0)
    dcg = sum((2 ** gold_rel.get(d, 0) - 1) / math.log2(i + 2) for i, d in enumerate(ids))
    ideal = sorted(gold_rel.values(), reverse=True)
    idcg_v = sum((2**rv - 1) / math.log2(i + 2) for i, rv in enumerate(ideal[:10]))
    ndcg = dcg / idcg_v if idcg_v else 0.0
    h, ap = 0, 0.0
    for i, d in enumerate(ids):
        if d in gold_set:
            h += 1
            ap += h / (i + 1)
    ap = ap / r if r else 0.0
    return r10, p5, mrr, ndcg, ap


def run(name, retriever_fn, queries, rel_map, reranker=None):
    R = {"Recall@10": [], "Precision@5": [], "MRR": [], "MAP": [], "nDCG@10": []}
    lat, nctx = [], 0
    for q in queries:
        gold = rel_map.get(q["qid"], [])
        gs = {r["doc_id"] for r in gold}
        gr = {r["doc_id"]: r["relevance"] for r in gold}
        s = time.monotonic()
        results = retriever_fn(q["query"], 10)
        if reranker:
            results = reranker.rerank(q["query"], results)
        lat.append((time.monotonic() - s) * 1000)
        sc = 0.0
        if results:
            if reranker:
                sc = results[0].get("reranker_score", 0)
            else:
                sc = results[0].get("hybrid_score", results[0].get("score", 0))
        thr = 0.0 if reranker and "CrossEncoder" in type(reranker).__name__ else 0.6
        if not results or sc < thr:
            nctx += 1
        r10, p5, mrr, ndcg, ap = metrics(results, gs, gr)
        R["Recall@10"].append(r10)
        R["Precision@5"].append(p5)
        R["MRR"].append(mrr)
        R["MAP"].append(ap)
        R["nDCG@10"].append(ndcg)
    sl = sorted(lat)
    n = len(sl)
    return {k: round(statistics.mean(v), 4) for k, v in R.items()} | {
        "P50": round(sl[max(0, int(n * 0.50))], 2),
        "P95": round(sl[max(0, int(n * 0.95))], 2),
        "P99": round(sl[max(0, int(n * 0.99))], 2),
        "Throughput": round(len(queries) / (sum(lat) / 1000), 2),
        "No-context": round(nctx / len(queries), 4),
    }


BASELINES = {
    "Vector only": {"R@10": 0.6700, "MAP": 0.9423, "nDCG": 0.8346, "P95": 195.57, "NoCtx": 0.215},
    "Hybrid": {"R@10": 0.8708, "MAP": 0.6444, "nDCG": 0.6498, "P95": 200.27, "NoCtx": 0.005},
}


def main() -> int:
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient
    from motor.intelligence.reranking.ce import CrossEncoderReranker
    from motor.intelligence.retrieval.hybrid import HybridRetriever
    from motor.intelligence.retrieval.lexical import LexicalRetriever
    from motor.intelligence.retrieval.vector import VectorRetriever

    cfg = UraConfig()
    qc = QdrantClient.instancia(cfg)
    if not qc.disponible:
        return 1

    queries, rel_map = load()
    vec = VectorRetriever(qc)
    lex = LexicalRetriever()
    hybrid = HybridRetriever(vec, lex, alpha=0.7, beta=0.3)
    ce = CrossEncoderReranker(top_k=10, batch_size=10)

    configs = {
        "Vector-only": vec.search,
        "Hybrid (score)": hybrid.search,
        "Hybrid + CrossEncoder": hybrid.search,
    }

    results = {}
    for name, fn in configs.items():
        rr = ce if "CrossEncoder" in name else None
        results[name] = run(name, fn, queries, rel_map, reranker=rr)

    for name in configs:
        r = results[name]

    # Acceptance for Hybrid+CrossEncoder
    r = results["Hybrid + CrossEncoder"]
    b = BASELINES
    checks = [
        ("MAP >= Vector-only", r["MAP"] >= b["Vector only"]["MAP"], f"{r['MAP']:.4f} >= {b['Vector only']['MAP']:.4f}"),
        (
            "nDCG >= Vector-only",
            r["nDCG@10"] >= b["Vector only"]["nDCG"],
            f"{r['nDCG@10']:.4f} >= {b['Vector only']['nDCG']:.4f}",
        ),
        ("R@10 >= Hybrid", r["Recall@10"] >= b["Hybrid"]["R@10"], f"{r['Recall@10']:.4f} >= {b['Hybrid']['R@10']:.4f}"),
        (
            "NoCtx <= Hybrid",
            r["No-context"] <= b["Hybrid"]["NoCtx"],
            f"{r['No-context']:.2%} <= {b['Hybrid']['NoCtx']:.2%}",
        ),
        (
            "P95 <= Hybrid +25%",
            r["P95"] <= b["Hybrid"]["P95"] * 1.25,
            f"{r['P95']:.2f} <= {b['Hybrid']['P95'] * 1.25:.2f}",
        ),
    ]
    all_pass = True
    for _label, passed, _detail in checks:
        if not passed:
            all_pass = False

    if all_pass:
        pass
    else:
        pass

    if all_pass:
        pass
    else:
        pass

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
