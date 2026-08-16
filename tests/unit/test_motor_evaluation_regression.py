"""Tests para motor/core/evaluation/ — continuous y regression."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from motor.core.evaluation.continuous import ContinuousEvaluationResult, ContinuousEvaluator
from motor.core.evaluation.corpus import EvaluationCorpus, EvaluationQuery
from motor.core.evaluation.regression import (
    RegressionBaseline,
    RegressionDetector,
    RegressionFinding,
    RegressionReport,
)


class TestRegressionFinding:
    def test_direction_y_change(self) -> None:
        f = RegressionFinding("cfg", "recall", 0.8, 0.6, -0.05)
        assert f.direction == "down"
        assert f.change_pct == pytest.approx(-25.0, abs=0.1)
        assert f.is_regression() is True  # bajó >5%

    def test_subida_no_regresion(self) -> None:
        f = RegressionFinding("cfg", "recall", 0.5, 0.7, -0.05)
        assert f.is_regression() is False

    def test_latencia_subida_es_regresion(self) -> None:
        f = RegressionFinding("cfg", "latency_p50", 10.0, 15.0, 0.10)
        assert f.is_regression() is True  # subió >10%

    def test_baseline_cero_no_regresion(self) -> None:
        f = RegressionFinding("cfg", "recall", 0.0, 0.5, -0.05)
        assert f.is_regression() is False

    def test_to_dict_y_repr(self) -> None:
        f = RegressionFinding("cfg", "recall", 0.8, 0.6, -0.05)
        d = f.to_dict()
        assert d["config"] == "cfg"
        assert "cfg" in repr(f)
        assert d == {
            "config": "cfg",
            "metric": "recall",
            "baseline": 0.8,
            "current": 0.6,
            "change_pct": -25.0,
            "threshold_pct": -5.0,
            "direction": "down",
            "is_regression": True,
        }
        assert "🔴" in repr(f)

    def test_redondeo_valores(self) -> None:
        f = RegressionFinding("c", "mrr", 0.81234, 0.60678, -0.05)
        assert f.baseline_value == 0.8123
        assert f.current_value == 0.6068
        assert f.change_pct == pytest.approx(-25.3, abs=0.1)

    def test_latencia_baja_no_regresion(self) -> None:
        f = RegressionFinding("c", "latency_p95", 20.0, 15.0, 0.20)
        assert f.is_regression() is False  # bajó = mejora
        assert f.direction == "down"

    def test_latencia_subida_dentro_umbral(self) -> None:
        f = RegressionFinding("c", "latency_p50", 10.0, 10.5, 0.10)
        assert f.is_regression() is False  # +5% < 10%


class TestRegressionReport:
    def test_passed_y_totales(self) -> None:
        ok = RegressionFinding("c", "recall", 0.8, 0.7, -0.05)  # no regression
        bad = RegressionFinding("c", "mrr", 0.8, 0.5, -0.05)  # regression
        rep = RegressionReport("base", 1.0, [ok, bad], 1, 2)
        assert rep.total_regressions == 2  # ambos bajaron >5%
        assert rep.passed is False
        d = rep.to_dict()
        assert d["total_findings"] == 2
        assert d["total_regressions"] == 2

    def test_passed_true(self) -> None:
        rep = RegressionReport("base", 1.0, [], 1, 2)
        assert rep.passed is True

    def test_to_dict_y_summary(self) -> None:
        rep = RegressionReport("base", 1.0, [], 2, 3)
        d = rep.to_dict()
        assert d["total_configs"] == 2
        assert "PASS" in rep.summary()
        assert "Configs: 2" in rep.summary()

    def test_summary_con_findings(self) -> None:
        bad = RegressionFinding("c", "mrr", 0.8, 0.5, -0.05)
        rep = RegressionReport("base", 1.0, [bad], 1, 1)
        s = rep.summary()
        assert "FAIL" in s
        assert "c.mrr" in s
        assert rep.to_dict()["total_regressions"] == 1


class TestRegressionBaseline:
    def test_set_get(self) -> None:
        b = RegressionBaseline("b1")
        b.set("cfg", "recall", 0.8)
        assert b.get("cfg", "recall") == 0.8
        assert b.get("cfg", "nope") is None
        assert b.name == "b1"

    def test_set_results_con_objects(self) -> None:
        b = RegressionBaseline()
        r = SimpleNamespace(config_name="cfg", metrics={"recall@10": 0.8}, latency_stats={"mean_ms": 5.0, "max_ms": 10.0})
        b.set_results([r])
        assert b.get("cfg", "recall@10") == 0.8
        assert b.get("cfg", "latency_p50") == 5.0
        assert b.get("cfg", "latency_p95") == 10.0
        assert b.get("cfg", "throughput") is not None

    def test_set_results_con_dicts(self) -> None:
        b = RegressionBaseline()
        r = {"config": "cfg", "metrics": {"mrr": 0.5}, "latency_stats": {}}
        b.set_results([r])
        assert b.get("cfg", "mrr") == 0.5

    def test_save_load(self, tmp_path) -> None:
        b = RegressionBaseline("base1")
        b.set("cfg", "recall", 0.75)
        p = tmp_path / "baseline.json"
        b.save(p)
        b2 = RegressionBaseline.load(p)
        assert b2.name == "base1"
        assert b2.get("cfg", "recall") == 0.75
        assert b2._created_at == b._created_at  # type: ignore[attr-defined]
        assert b2._updated_at == b._updated_at  # type: ignore[attr-defined]

    def test_load_sin_timestamps(self, tmp_path) -> None:
        p = tmp_path / "b2.json"
        p.write_text(json.dumps({"baselines": {"cfg.recall": 0.9}}))
        b = RegressionBaseline.load(p)
        assert b.name == "loaded"
        assert b.get("cfg", "recall") == 0.9

    def test_set_results_throughput(self) -> None:
        b = RegressionBaseline()
        r = SimpleNamespace(
            config_name="cfg",
            metrics={"recall@10": 0.8},
            latency_stats={"mean_ms": 5.0, "max_ms": 10.0},
        )
        b.set_results([r])
        # throughput = len(self._data) / mean_ms * 1000 (placeholder interno)
        assert b.get("cfg", "throughput") == pytest.approx(3 / 5 * 1000)

    def test_set_results_sin_latencia(self) -> None:
        b = RegressionBaseline()
        r = SimpleNamespace(config_name="cfg", metrics={"recall@10": 0.8}, latency_stats={})
        b.set_results([r])
        assert b.get("cfg", "latency_p50") is None
        assert b.get("cfg", "throughput") is None

    def test_to_dict(self) -> None:
        b = RegressionBaseline("n")
        b.set("a", "m", 1.0)
        d = b.to_dict()
        assert d["baselines"] == {"a.m": 1.0}


class TestRegressionDetector:
    def test_sin_regresion(self) -> None:
        b = RegressionBaseline("base")
        b.set("cfg", "recall@10", 0.8)
        r = SimpleNamespace(config_name="cfg", metrics={"recall@10": 0.8}, latency_stats={})
        rep = RegressionDetector(b).check([r])
        assert rep.passed is True

    def test_con_regresion(self) -> None:
        b = RegressionBaseline("base")
        b.set("cfg", "recall@10", 0.8)
        r = SimpleNamespace(config_name="cfg", metrics={"recall@10": 0.5}, latency_stats={})
        rep = RegressionDetector(b).check([r])
        assert rep.passed is False
        assert rep.total_regressions == 1

    def test_metric_sin_baseline_se_omite(self) -> None:
        b = RegressionBaseline("base")
        r = SimpleNamespace(config_name="cfg", metrics={"recall@10": 0.8}, latency_stats={})
        rep = RegressionDetector(b).check([r])
        assert rep.total_regressions == 0

    def test_latencia_regresion(self) -> None:
        b = RegressionBaseline("base")
        b.set("cfg", "latency_p50", 5.0)
        r = SimpleNamespace(config_name="cfg", metrics={}, latency_stats={"mean_ms": 10.0})
        rep = RegressionDetector(b).check([r])
        assert rep.passed is False

    def test_thresholds_personalizados(self) -> None:
        b = RegressionBaseline("base")
        b.set("cfg", "recall@10", 0.8)
        r = SimpleNamespace(config_name="cfg", metrics={"recall@10": 0.7}, latency_stats={})
        rep = RegressionDetector(b, thresholds={"recall": -0.30}).check([r])
        assert rep.passed is True  # bajó 12.5% < 30%

    def test_dicts_input(self) -> None:
        b = RegressionBaseline("base")
        b.set("cfg", "mrr", 0.5)
        r = {"config": "cfg", "metrics": {"mrr": 0.4}, "latency_stats": {}}
        rep = RegressionDetector(b).check([r])
        assert rep.total_regressions == 1


class TestContinuousEvaluationResult:
    def test_passed_y_to_dict(self) -> None:
        r = ContinuousEvaluationResult("exp", "pass", {"m": 1}, None, [], 1.5, [])
        assert r.passed is True
        d = r.to_dict()
        assert d["status"] == "pass"
        assert d["elapsed_seconds"] == 1.5

    def test_no_passed(self) -> None:
        r = ContinuousEvaluationResult("exp", "fail", {}, None, [], 0.0, [])
        assert r.passed is False

    def test_save(self, tmp_path) -> None:
        r = ContinuousEvaluationResult("exp", "pass", {}, None, [], 1.0, [])
        p = tmp_path / "res.json"
        r.save(p)
        assert json.loads(p.read_text())["experiment"] == "exp"


class TestContinuousEvaluator:
    @pytest.fixture
    def corpus(self) -> EvaluationCorpus:
        c = EvaluationCorpus("t")
        c.add_query(EvaluationQuery("q1", "buscar gpu", {"d1"}))
        return c

    def test_configs(self, corpus) -> None:
        ev = ContinuousEvaluator("rag")
        ev.add_config("bm25", lambda q: ["d1"], {"k": 1}, "desc")
        assert len(ev._configs) == 1

    def test_setters(self, corpus) -> None:
        ev = ContinuousEvaluator()
        ev.set_fail_on_regression(False)
        ev.set_critical_thresholds({"recall": -0.1})
        assert ev._fail_on_regression is False
        assert ev._critical_thresholds == {"recall": -0.1}

    def test_run_sin_baseline(self, corpus) -> None:
        ev = ContinuousEvaluator("rag")
        ev.add_config("bm25", lambda q: ["d1"])
        res = ev.run(corpus, k=10)
        assert res.status == "pass"
        assert res.passed is True
        assert "rankings" in res.metrics_summary

    def test_run_corpus_vacio(self) -> None:
        ev = ContinuousEvaluator("rag")
        ev.add_config("bm25", lambda q: [])
        res = ev.run(EvaluationCorpus("vacio"), k=10)
        assert any("Corpus vacío" in e for e in res.errors)
        assert res.status == "warning"

    def test_run_con_baseline_path(self, corpus, tmp_path) -> None:
        ev = ContinuousEvaluator("rag")
        ev.add_config("bm25", lambda q: ["d1"])
        p = tmp_path / "baseline.json"
        res = ev.run(corpus, k=10, baseline_path=str(p))
        assert res.regression_report is None  # sin baseline previo: crea nueva
        assert p.exists()  # baseline guardada

    def test_run_con_regresion_fail(self, corpus, tmp_path) -> None:
        ev = ContinuousEvaluator("rag")
        ev.add_config("bm25", lambda q: ["d1"])
        p = tmp_path / "baseline.json"
        ev.run(corpus, k=10, baseline_path=str(p))  # crea baseline buena
        # segunda ejecucion con retriever peor
        ev2 = ContinuousEvaluator("rag")
        ev2.add_config("bm25", lambda q: ["nada"])
        res2 = ev2.run(corpus, k=10, baseline_path=str(p))
        assert res2.status == "fail"

    def test_run_warning_sin_fail_on_regression(self, corpus, tmp_path) -> None:
        ev = ContinuousEvaluator("rag")
        ev.add_config("bm25", lambda q: ["d1"])
        p = tmp_path / "baseline.json"
        ev.run(corpus, k=10, baseline_path=str(p))
        ev2 = ContinuousEvaluator("rag")
        ev2.set_fail_on_regression(False)
        ev2.add_config("bm25", lambda q: ["nada"])
        res2 = ev2.run(corpus, k=10, baseline_path=str(p))
        assert res2.status == "warning"
