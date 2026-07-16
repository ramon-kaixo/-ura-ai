"""Tests del framework de evaluación RAG (F21-B1).

Verifica:
1. Recall@K, Precision@K
2. MRR
3. MAP
4. nDCG@K
5. Múltiples corpus
6. Exportación JSON
7. Thread-safety
8. Independencia del router/pipeline
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path  # noqa: TC003

from motor.core.evaluation import EvaluationEngine
from motor.core.evaluation.corpus import EvaluationCorpus, EvaluationQuery
from motor.core.evaluation.metrics import (
    map_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


class TestMetrics:
    """Tests unitarios de cada métrica."""

    def test_recall_at_k(self) -> None:
        relevant = {"d1", "d3"}
        retrieved = ["d1", "d2", "d3", "d4", "d5"]
        assert recall_at_k(relevant, retrieved, 1) == 0.5  # 1/2
        assert recall_at_k(relevant, retrieved, 2) == 0.5  # 1/2
        assert recall_at_k(relevant, retrieved, 3) == 1.0  # 2/2
        assert recall_at_k(relevant, retrieved, 5) == 1.0

    def test_recall_at_k_empty(self) -> None:
        assert recall_at_k(set(), ["d1"], 5) == 0.0
        assert recall_at_k({"d1"}, [], 5) == 0.0

    def test_precision_at_k(self) -> None:
        relevant = {"d1", "d3"}
        retrieved = ["d1", "d2", "d3", "d4", "d5"]
        assert precision_at_k(relevant, retrieved, 1) == 1.0  # 1/1
        assert precision_at_k(relevant, retrieved, 2) == 0.5  # 1/2
        assert precision_at_k(relevant, retrieved, 3) == 2.0 / 3  # 2/3
        assert precision_at_k(relevant, retrieved, 5) == 2.0 / 5

    def test_precision_at_k_empty(self) -> None:
        assert precision_at_k(set(), ["d1"], 5) == 0.0
        assert precision_at_k({"d1"}, [], 5) == 0.0
        assert precision_at_k({"d1"}, ["d1"], 0) == 0.0

    def test_mrr(self) -> None:
        relevant = {"d3"}
        assert mrr(relevant, ["d1", "d2", "d3", "d4"]) == 1.0 / 3
        assert mrr(relevant, ["d3", "d1", "d2"]) == 1.0
        assert mrr(relevant, ["d1", "d2"]) == 0.0  # No relevant
        assert mrr(set(), ["d1"]) == 0.0  # Empty relevant

    def test_mrr_first(self) -> None:
        relevant = {"d1"}
        assert mrr(relevant, ["d1", "d2", "d3"]) == 1.0

    def test_map_at_k(self) -> None:
        q1 = ({"d1", "d3"}, ["d1", "d2", "d3"])
        q2 = ({"d2"}, ["d2", "d1"])
        result = map_at_k([q1, q2], k=3)
        # AP q1: (1/1 + 2/3) / 2 = 0.833
        # AP q2: (1/1) / 1 = 1.0
        # MAP: (0.833 + 1.0) / 2 = 0.916
        assert round(result, 3) == 0.917

    def test_map_at_k_empty(self) -> None:
        assert map_at_k([], 10) == 0.0

    def test_ndcg_at_k(self) -> None:
        relevant = {"d1", "d2", "d3"}
        retrieved = ["d1", "d4", "d2", "d5", "d3"]
        result = ndcg_at_k(relevant, retrieved, k=5)
        # DCG: d1=1 (pos1), d4=0 (pos2), d2=1 (pos3), d5=0 (pos4), d3=1 (pos5)
        # i=1: 1, i=2: 0, i=3: 1/log2(3)=0.63, i=4: 0, i=5: 1/log2(5)=0.43
        # DCG = 1 + 0 + 0.63 + 0 + 0.43 = 2.06
        # IDCG: 1 + 1/log2(3) + 1/log2(4) = 1 + 0.63 + 0.5 = 2.13
        # nDCG = 2.06 / 2.13 ≈ 0.97
        assert 0.7 <= result <= 1.0, f"nDCG={result}"

    def test_ndcg_at_k_perfect(self) -> None:
        relevant = {"d1", "d2"}
        retrieved = ["d1", "d2", "d3"]
        result = ndcg_at_k(relevant, retrieved, k=3)
        assert result == 1.0  # Perfect ranking

    def test_ndcg_at_k_graded(self) -> None:
        relevant = {"d1", "d2"}
        retrieved = ["d1", "d2", "d3"]
        scores = {"d1": 0.5, "d2": 1.0}
        result = ndcg_at_k(relevant, retrieved, k=3, relevance_scores=scores)
        # Ambos docs son relevantes y están en orden ideal → nDCG=1.0
        assert result == 1.0

    def test_ndcg_at_k_empty(self) -> None:
        assert ndcg_at_k(set(), ["d1"], 5) == 0.0
        assert ndcg_at_k({"d1"}, [], 5) == 0.0

    def test_ndcg_at_k_no_relevant_in_results(self) -> None:
        relevant = {"d99"}
        retrieved = ["d1", "d2", "d3"]
        result = ndcg_at_k(relevant, retrieved, k=3)
        assert result == 0.0


class TestEvaluationCorpus:
    def test_corpus_add_query(self) -> None:
        corpus = EvaluationCorpus("test")
        q = EvaluationQuery("q1", "test query", {"d1", "d2"})
        corpus.add_query(q)
        assert len(corpus) == 1
        assert corpus.get_query("q1") is not None

    def test_corpus_to_dict(self) -> None:
        corpus = EvaluationCorpus("test")
        corpus.add_query(EvaluationQuery("q1", "text", {"d1"}))
        d = corpus.to_dict()
        assert d["name"] == "test"
        assert len(d["queries"]) == 1

    def test_corpus_save_load(self, tmp_path: Path) -> None:
        corpus = EvaluationCorpus("test")
        corpus.add_query(EvaluationQuery("q1", "text", {"d1"}))
        path = tmp_path / "corpus.json"
        corpus.save(str(path))

        loaded = EvaluationCorpus.load(str(path))
        assert loaded.name == "test"
        assert len(loaded) == 1
        q = loaded.get_query("q1")
        assert q is not None
        assert q.query_text == "text"
        assert "d1" in q.relevant_docs

    def test_multiple_queries(self) -> None:
        corpus = EvaluationCorpus("multi")
        queries = [
            EvaluationQuery(f"q{i}", f"text{i}", {f"d{i}"})
            for i in range(3)
        ]
        corpus.add_queries(queries)
        assert len(corpus) == 3


class TestEvaluationEngine:
    def test_engine_register(self) -> None:
        engine = EvaluationEngine()
        corpus = EvaluationCorpus("c1")
        engine.register_corpus("c1", corpus)
        assert "c1" in engine.list_corpora()

    def test_engine_evaluate(self) -> None:
        corpus = EvaluationCorpus("test")
        corpus.add_query(EvaluationQuery("q1", "test", {"d1", "d3"}))

        def _retriever(query: str) -> list[str]:
            return ["d1", "d2", "d3"]

        engine = EvaluationEngine()
        engine.register_corpus("test", corpus)
        engine.register_retriever("bm25", _retriever)

        run = engine.evaluate("test", "bm25", k=3)
        assert run.metrics["recall@3"] == 1.0  # All relevant retrieved
        assert run.metrics["mrr"] == 1.0  # d1 is first
        assert run.metrics["precision@3"] == 2.0 / 3

    def test_engine_evaluate_partial(self) -> None:
        corpus = EvaluationCorpus("test")
        corpus.add_query(EvaluationQuery("q1", "test", {"d1", "d2", "d3"}))

        def _bad_retriever(query: str) -> list[str]:
            return ["d4", "d5", "d6"]

        engine = EvaluationEngine()
        engine.register_corpus("test", corpus)
        engine.register_retriever("bad", _bad_retriever)

        run = engine.evaluate("test", "bad", k=3)
        assert run.metrics["recall@3"] == 0.0
        assert run.metrics["mrr"] == 0.0

    def test_engine_multiple_queries(self) -> None:
        corpus = EvaluationCorpus("multi")
        corpus.add_query(EvaluationQuery("q1", "a", {"d1"}))
        corpus.add_query(EvaluationQuery("q2", "b", {"d2"}))

        def _retriever(query: str) -> list[str]:
            if "a" in query:
                return ["d1", "d2"]
            return ["d2", "d1"]

        engine = EvaluationEngine()
        engine.register_corpus("multi", corpus)
        engine.register_retriever("r", _retriever)
        run = engine.evaluate("multi", "r", k=2)
        assert run.metrics["recall@2"] == 1.0

    def test_engine_invalid_corpus(self) -> None:
        engine = EvaluationEngine()
        import pytest
        with pytest.raises(ValueError):
            engine.evaluate("nonexistent", "r")

    def test_engine_invalid_retriever(self) -> None:
        engine = EvaluationEngine()
        engine.register_corpus("c", EvaluationCorpus())
        import pytest
        with pytest.raises(ValueError):
            engine.evaluate("c", "nonexistent")

    def test_engine_compare(self) -> None:
        corpus = EvaluationCorpus("c")
        corpus.add_query(EvaluationQuery("q1", "test", {"d1"}))

        def _retriever_a(query: str) -> list[str]:
            return ["d1", "d2"]

        def _retriever_b(query: str) -> list[str]:
            return ["d2", "d1"]

        engine = EvaluationEngine()
        engine.register_corpus("c", corpus)
        engine.register_retriever("a", _retriever_a)
        engine.register_retriever("b", _retriever_b)

        comparison = engine.compare("c", ["a", "b"], k=2)
        assert "configs" in comparison
        assert "a" in comparison["configs"]
        assert "b" in comparison["configs"]
        # 'a' should be better for recall@2 (d1 is relevant)
        assert comparison["best_by_metric"]["recall@2"]["config"] == "a"

    def test_engine_json_export(self, tmp_path: Path) -> None:
        corpus = EvaluationCorpus("c")
        corpus.add_query(EvaluationQuery("q1", "test", {"d1"}))

        def _retriever(query: str) -> list[str]:
            return ["d1"]

        engine = EvaluationEngine()
        engine.register_corpus("c", corpus)
        engine.register_retriever("r", _retriever)
        engine.evaluate("c", "r", k=1)

        path = tmp_path / "results.json"
        engine.save_results(str(path))
        assert path.exists()

        data = json.loads(path.read_text())
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["metrics"]["recall@1"] == 1.0

    def test_engine_json_load(self, tmp_path: Path) -> None:
        # Save from engine A
        corpus = EvaluationCorpus("c")
        corpus.add_query(EvaluationQuery("q1", "test", {"d1"}))
        engine_a = EvaluationEngine()
        engine_a.register_corpus("c", corpus)
        engine_a.register_retriever("r", lambda q: ["d1"])
        engine_a.evaluate("c", "r", k=1)

        path = tmp_path / "results.json"
        engine_a.save_results(str(path))

        # Load into engine B
        engine_b = EvaluationEngine()
        engine_b.load_results(str(path))
        results = engine_b.get_results(10)
        assert len(results) == 1
        assert results[0]["metrics"]["recall@1"] == 1.0

    def test_engine_reset(self) -> None:
        engine = EvaluationEngine()
        corpus = EvaluationCorpus("c")
        corpus.add_query(EvaluationQuery("q1", "t", {"d1"}))
        engine.register_corpus("c", corpus)
        engine.register_retriever("r", lambda q: ["d1"])
        engine.evaluate("c", "r")
        assert len(engine.get_results()) == 1
        engine.reset()
        assert len(engine.get_results()) == 0

    def test_router_independence(self) -> None:
        """El evaluador no depende del router LLM."""
        import motor.core.evaluation as ev  # noqa: F811
        import inspect

        src = inspect.getsource(ev)
        assert "motor.core.llm.router" not in src, (
            "evaluation module should not import motor.core.llm.router"
        )


class TestThreadSafety:
    def test_corpus_thread_safe(self) -> None:
        corpus = EvaluationCorpus("conc")

        def _add(i: int) -> None:
            corpus.add_query(EvaluationQuery(f"q{i}", f"text{i}", {f"d{i}"}))

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_add, i) for i in range(20)]
            for f in futures:
                f.result()

        assert len(corpus) == 20

    def test_engine_thread_safe(self) -> None:
        corpus = EvaluationCorpus("conc")
        corpus.add_query(EvaluationQuery("q1", "test", {"d1"}))

        engine = EvaluationEngine()
        engine.register_corpus("conc", corpus)
        engine.register_retriever("r", lambda q: ["d1"])

        def _eval(i: int) -> None:
            engine.evaluate("conc", "r", k=1)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_eval, i) for i in range(10)]
            for f in futures:
                f.result()

        results = engine.get_results(100)
        assert len(results) == 10
