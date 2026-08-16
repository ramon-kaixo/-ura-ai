"""Tests para motor/core/evaluation/ — evaluator y experiment."""
from __future__ import annotations

import pytest

from motor.core.evaluation.corpus import EvaluationCorpus, EvaluationQuery
from motor.core.evaluation.evaluator import EvaluationEngine, EvaluationRun, RetrievalResult
from motor.core.evaluation.experiment import Experiment, ExperimentConfig, ExperimentResult


def _corpus() -> EvaluationCorpus:
    c = EvaluationCorpus("test")
    c.add_query(EvaluationQuery("q1", "buscar gpu", {"d1", "d2"}, {"d1": 1.0, "d2": 0.5}))
    c.add_query(EvaluationQuery("q2", "buscar ram", {"d3"}))
    return c


def _retriever(query_text: str) -> list[str]:
    if "gpu" in query_text:
        return ["d1", "x", "d2"]
    return ["d3", "y"]


class TestRetrievalResult:
    def test_slots(self) -> None:
        r = RetrievalResult("q1", ["a"], 5.0)
        assert r.query_id == "q1"
        assert r.retrieved == ["a"]
        assert r.latency_ms == 5.0


class TestEvaluationRun:
    def test_to_dict(self) -> None:
        run = EvaluationRun("corpus", "cfg", {"recall@10": 1.0}, [{"q": 1}], 123.0, {"mean": 5.0})
        d = run.to_dict()
        assert d["corpus"] == "corpus"
        assert d["metrics"]["recall@10"] == 1.0
        assert d["latency_stats"] == {"mean": 5.0}


class TestEvaluationEngine:
    def test_registros_y_listas(self) -> None:
        e = EvaluationEngine()
        c = _corpus()
        e.register_corpus("c1", c)
        e.register_retriever("r1", _retriever)
        assert e.list_corpora() == ["c1"]
        assert e.list_retrievers() == ["r1"]

    def test_evaluate(self) -> None:
        e = EvaluationEngine()
        e.register_corpus("c1", _corpus())
        e.register_retriever("r1", _retriever)
        run = e.evaluate("c1", "r1", k=2)
        assert isinstance(run, EvaluationRun)
        assert "recall@2" in run.metrics
        assert len(run.per_query) == 2
        assert "mean_ms" in run.latency_stats
        # q1: relevant {d1,d2}, retrieved [d1,x,d2], top2 [d1,x] → recall=0.5, prec=0.5, mrr=1.0
        # q2: relevant {d3}, retrieved [d3,y], top2 [d3,y] → recall=1.0, prec=0.5, mrr=1.0
        assert run.metrics["recall@2"] == 0.75
        assert run.metrics["precision@2"] == 0.5
        assert run.metrics["mrr"] == 1.0
        assert run.per_query[0]["query_id"] == "q1"
        assert run.per_query[0]["query_text"] == "buscar gpu"
        assert run.per_query[0]["latency_ms"] >= 0
        assert run.timestamp > 0
        assert run.config_name == "r1"
        assert run.corpus_name == "c1"

    def test_latencia_stats_vacio(self) -> None:
        from motor.core.evaluation.evaluator import _latencia_stats

        stats = _latencia_stats([])
        assert stats == {"mean_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}

    def test_agregar_sin_queries(self) -> None:
        from motor.core.evaluation.evaluator import _agregar

        agg = _agregar([], [], 5, 1)
        assert agg["map"] == 0.0
        assert agg["recall@5"] == 0.0

    def test_evaluate_corpus_no_existe(self) -> None:
        e = EvaluationEngine()
        e.register_retriever("r1", _retriever)
        with pytest.raises(ValueError, match="Corpus not found"):
            e.evaluate("nope", "r1")

    def test_evaluate_retriever_no_existe(self) -> None:
        e = EvaluationEngine()
        e.register_corpus("c1", _corpus())
        with pytest.raises(ValueError, match="Retriever not found"):
            e.evaluate("c1", "nope")

    def test_evaluate_relevance_scores(self) -> None:
        e = EvaluationEngine()
        e.register_corpus("c1", _corpus())
        e.register_retriever("r1", _retriever)
        run = e.evaluate("c1", "r1", k=2, relevance_scores=True)
        assert run is not None

    def test_max_results(self) -> None:
        e = EvaluationEngine()
        e._max_results = 2
        e.register_corpus("c1", _corpus())
        e.register_retriever("r1", _retriever)
        for _ in range(4):
            e.evaluate("c1", "r1")
        assert len(e._results) == 2

    def test_compare(self) -> None:
        e = EvaluationEngine()
        e.register_corpus("c1", _corpus())
        e.register_retriever("r1", _retriever)
        e.register_retriever("r2", lambda q: ["d1", "d3"])
        comp = e.compare("c1", ["r1", "r2"], k=2)
        assert "best_by_metric" in comp
        assert "r1" in comp["configs"]
        assert "r2" in comp["configs"]
        assert comp["corpus"] == "c1"
        assert set(comp["best_by_metric"]) == {"recall@2", "precision@2", "mrr", "ndcg@2", "map"}
        for info in comp["best_by_metric"].values():
            assert info["config"] in {"r1", "r2"}
            assert isinstance(info["value"], float)

    def test_get_results_y_save_load(self, tmp_path) -> None:
        e = EvaluationEngine()
        e.register_corpus("c1", _corpus())
        e.register_retriever("r1", _retriever)
        e.evaluate("c1", "r1")
        results = e.get_results()
        assert len(results) == 1
        p = tmp_path / "results.json"
        e.save_results(p)
        e2 = EvaluationEngine()
        e2.load_results(p)
        assert len(e2.get_results()) == 1

    def test_reset(self) -> None:
        e = EvaluationEngine()
        e.register_corpus("c1", _corpus())
        e.register_retriever("r1", _retriever)
        e.evaluate("c1", "r1")
        e.reset()
        assert e.get_results() == []


class TestExperiment:
    def test_propiedades(self) -> None:
        exp = Experiment("exp1", _corpus(), "desc")
        assert exp.name == "exp1"
        assert exp.configs == []
        assert exp.results == []

    def test_add_config_y_run(self) -> None:
        exp = Experiment("exp1", _corpus())
        exp.add_config("bm25", _retriever, {"k1": 1.2}, "config bm25")
        exp.add_config("sem", lambda q: ["d1", "d2"], {"m": "x"})
        results = exp.run(k=2)
        assert len(results) == 2
        assert all(isinstance(r, ExperimentResult) for r in results)
        assert exp.results == results

    def test_compare_despues_run(self) -> None:
        exp = Experiment("exp1", _corpus())
        exp.add_config("bm25", _retriever)
        exp.add_config("sem", lambda q: ["d1", "d2"])
        exp.run(k=2)
        comp = exp.compare()
        assert comp["total_configs"] == 2
        assert comp["winner"] in ("bm25", "sem")
        assert len(comp["general_ranking"]) == 2

    def test_compare_sin_results(self) -> None:
        exp = Experiment("exp1", _corpus())
        assert exp.compare() == {"error": "no results", "configs": []}

    def test_report(self) -> None:
        exp = Experiment("exp1", _corpus())
        exp.add_config("bm25", _retriever)
        exp.run(k=2)
        rep = exp.report()
        assert "Experimento: exp1" in rep
        assert "Ganador" in rep

    def test_report_sin_results(self) -> None:
        exp = Experiment("exp1", _corpus())
        assert "Error" in exp.report()

    def test_to_dict_save_load(self, tmp_path) -> None:
        exp = Experiment("exp1", _corpus())
        exp.add_config("bm25", _retriever)
        exp.run(k=2)
        d = exp.to_dict()
        assert d["experiment"] == "exp1"
        p = tmp_path / "exp.json"
        exp.save(p)
        loaded = Experiment.load(p)
        assert len(loaded["results"]) == 1
        assert loaded["experiment"] == "exp1"


class TestExperimentConfig:
    def test_acepta_args(self) -> None:
        cfg = ExperimentConfig("name", lambda q: [], {"k": 1}, "d")
        assert cfg.name == "name"
        assert cfg.params == {"k": 1}
