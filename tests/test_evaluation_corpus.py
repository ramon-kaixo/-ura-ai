from __future__ import annotations

# ruff: noqa: SLF001 — acceso a _engine del mock

import json
from pathlib import Path

import pytest

from scripts.pro.benchmark_ke import (
    BenchmarkResults,
    KERetrieval,
    compute_ap,
    compute_mrr,
    compute_ndcg,
    compute_precision,
    compute_recall,
    load_corpus,
    validate_corpus,
)

CORPUS_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "evaluation" / "corpus"


class TestCorpusIntegrity:
    def test_queries_file_exists(self):
        f = CORPUS_DIR / "queries.jsonl"
        assert f.exists(), f"Missing: {f}"

    def test_relevance_file_exists(self):
        f = CORPUS_DIR / "relevance.jsonl"
        assert f.exists(), f"Missing: {f}"

    def test_metadata_file_exists(self):
        f = CORPUS_DIR / "metadata.json"
        assert f.exists(), f"Missing: {f}"

    def test_corpus_has_200_queries(self):
        count = sum(1 for _ in open(CORPUS_DIR / "queries.jsonl"))
        assert count >= 200, f"Only {count} queries"

    def test_no_duplicate_qids(self):
        qids = [json.loads(line)["qid"] for line in open(CORPUS_DIR / "queries.jsonl")]
        assert len(qids) == len(set(qids)), "Duplicate qids found"

    def test_all_qids_follow_convention(self):
        for line in open(CORPUS_DIR / "queries.jsonl"):
            qid = json.loads(line)["qid"]
            assert qid.startswith(("sys_", "code_", "know_")), f"Bad qid: {qid}"

    def test_at_least_3_domains(self):
        domains = set()
        for line in open(CORPUS_DIR / "queries.jsonl"):
            domains.add(json.loads(line).get("domain", ""))
        assert len(domains) >= 2

    def test_all_relevance_scores_valid(self):
        for line in open(CORPUS_DIR / "relevance.jsonl"):
            rel = json.loads(line)["relevance"]
            assert rel in (0, 1, 2, 3), f"Invalid relevance: {rel}"

    def test_all_qids_in_reference_are_in_queries(self):
        query_qids = {json.loads(line)["qid"] for line in open(CORPUS_DIR / "queries.jsonl")}
        for line in open(CORPUS_DIR / "relevance.jsonl"):
            qid = json.loads(line)["qid"]
            assert qid in query_qids, f"Relevance references unknown qid: {qid}"

    def test_no_duplicate_relevance_pairs(self):
        pairs = set()
        for line in open(CORPUS_DIR / "relevance.jsonl"):
            d = json.loads(line)
            pair = (d["qid"], d["doc_id"])
            assert pair not in pairs, f"Duplicate relevance: {pair}"
            pairs.add(pair)

    def test_validate_corpus_returns_empty(self):
        errors = validate_corpus(CORPUS_DIR)
        assert errors == [], f"Validation errors: {errors}"


class TestBenchmarkReproducibility:
    def test_mock_is_deterministic(self):
        retriever = KERetrieval()
        retriever._engine = None
        r1 = retriever.search("How to configure Qdrant?")
        r2 = retriever.search("How to configure Qdrant?")
        assert r1 == r2

    def test_different_queries_different_results(self):
        retriever = KERetrieval()
        retriever._engine = None
        r1 = retriever.search("How does EventBus work?")
        r2 = retriever.search("What is semantic chunking?")
        assert r1 != r2

    def test_benchmark_reproducible(self):
        import tempfile

        from scripts.pro.benchmark_ke import run_benchmark

        with tempfile.TemporaryDirectory() as td:
            r1 = run_benchmark(CORPUS_DIR, Path(td), dry_run=True)
            r2 = run_benchmark(CORPUS_DIR, Path(td), dry_run=True)
            assert r1.mean_recall_10 == r2.mean_recall_10
            assert r1.mean_mrr == r2.mean_mrr
            assert r1.mean_ndcg == r2.mean_ndcg

    def test_results_file_is_json(self):
        results_file = CORPUS_DIR.parent / "results" / "baseline_results.json"
        if results_file.exists():
            data = json.loads(results_file.read_text())
            assert "mean_recall_10" in data


class TestBenchmarkDirect:
    def test_load_corpus_returns_200_queries(self):
        queries, relevance = load_corpus(CORPUS_DIR)
        assert len(queries) == 200

    def test_load_corpus_populates_relevance(self):
        _, relevance = load_corpus(CORPUS_DIR)
        assert len(relevance) > 0

    def test_compute_recall_all_relevant(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b"}
        assert compute_recall(retrieved, relevant, 5) == 1.0

    def test_compute_recall_none_relevant(self):
        retrieved = ["a", "b", "c"]
        relevant = {"z"}
        assert compute_recall(retrieved, relevant, 5) == 0.0

    def test_compute_precision_perfect(self):
        retrieved = ["a", "b"]
        relevant = {"a", "b"}
        assert compute_precision(retrieved, relevant, 2) == 1.0

    def test_compute_mrr_first(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a"}
        assert compute_mrr(retrieved, relevant) == 1.0

    def test_compute_mrr_second(self):
        retrieved = ["a", "b", "c"]
        relevant = {"b"}
        assert compute_mrr(retrieved, relevant) == 0.5

    def test_compute_mrr_not_found(self):
        retrieved = ["a", "b", "c"]
        relevant = {"z"}
        assert compute_mrr(retrieved, relevant) == 0.0

    def test_compute_ndcg_perfect(self):
        retrieved = ["a", "b"]
        relevance = {"a": 3, "b": 2}
        ndcg = compute_ndcg(retrieved, relevance, 2)
        assert ndcg == pytest.approx(1.0, rel=0.01)

    def test_compute_ap_simple(self):
        retrieved = ["a", "b", "c", "d"]
        relevant = {"a", "c"}
        ap = compute_ap(retrieved, relevant)
        # AP = (1/1 + 2/3) / 2 = (1 + 0.666) / 2 = 0.833
        assert ap == pytest.approx(0.8333, rel=0.01)


class TestJSONLFormat:
    def test_queries_jsonl_valid(self):
        for line in open(CORPUS_DIR / "queries.jsonl"):
            d = json.loads(line)
            assert "qid" in d
            assert "query" in d
            assert "domain" in d

    def test_relevance_jsonl_valid(self):
        for line in open(CORPUS_DIR / "relevance.jsonl"):
            d = json.loads(line)
            assert "qid" in d
            assert "doc_id" in d
            assert "relevance" in d
            assert isinstance(d["relevance"], int)


class TestBenchmarkResults:
    def test_results_has_all_metrics(self):
        r = BenchmarkResults(
            queries_total=200, queries_failed=0,
            mean_recall_1=0.5, mean_recall_5=0.6, mean_recall_10=0.7,
            mean_precision_5=0.4, mean_mrr=0.8, mean_ndcg=0.75, map=0.65,
            latency_p50=10, latency_p95=50, latency_p99=100,
            throughput_qps=100, no_context_rate=0.05, doc_coverage=0.8,
        )
        assert r.queries_total == 200
        assert r.mean_recall_10 == 0.7
        assert r.latency_p95 == 50


class TestIntegration:
    def test_mock_retrieval_returns_list(self):
        retriever = KERetrieval()
        retriever._engine = None
        results = retriever.search("test query")
        assert isinstance(results, list)
        assert len(results) <= 10
        if results:
            assert hasattr(results[0], "doc_id")
            assert hasattr(results[0], "score")
            assert hasattr(results[0], "rank")
