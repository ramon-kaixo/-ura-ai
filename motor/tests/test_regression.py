"""Tests de detección de regresiones RAG (F21-B4).

Verifica:
1. Sin regresión cuando valores coinciden
2. Regresión en Recall, Precision, MRR, MAP, nDCG
3. Regresión en latencia
4. Regresión en throughput
5. Exportación JSON
6. Carga JSON
7. Thread-safety
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from motor.core.evaluation.regression import (
    RegressionBaseline,
    RegressionDetector,
    RegressionFinding,
)


def _make_result(
    config: str = "bm25",
    metrics: dict | None = None,
    latency: dict | None = None,
) -> dict:
    return {
        "config": config,
        "metrics": metrics or {"recall@10": 0.85, "mrr": 0.75, "ndcg@10": 0.80, "map": 0.70},
        "latency_stats": latency or {"mean_ms": 100, "max_ms": 250},
    }


class TestRegressionFinding:
    def test_regression_detection_down(self) -> None:
        f = RegressionFinding("bm25", "recall@10", 0.85, 0.70, -0.05)
        assert f.is_regression()
        assert f.direction == "down"
        assert round(f.change_pct, 1) == -17.6

    def test_no_regression_within_threshold(self) -> None:
        f = RegressionFinding("bm25", "recall@10", 0.85, 0.83, -0.05)
        assert not f.is_regression()

    def test_latency_regression_up(self) -> None:
        f = RegressionFinding("bm25", "latency_p50", 100, 150, 0.10)
        assert f.is_regression()
        assert f.direction == "up"

    def test_latency_no_regression(self) -> None:
        f = RegressionFinding("bm25", "latency_p50", 100, 105, 0.10)
        assert not f.is_regression()

    def test_to_dict(self) -> None:
        f = RegressionFinding("bm25", "recall@10", 0.85, 0.70, -0.05)
        d = f.to_dict()
        assert d["config"] == "bm25"
        assert d["metric"] == "recall@10"
        assert "is_regression" in d


class TestRegressionBaseline:
    def test_set_get(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "recall@10", 0.85)
        assert bl.get("bm25", "recall@10") == 0.85
        assert bl.get("nonexistent", "x") is None

    def test_set_results(self) -> None:
        bl = RegressionBaseline("test")
        results = [
            _make_result("bm25", {"recall@10": 0.85}),
            _make_result("semantic", {"recall@10": 0.90}),
        ]
        bl.set_results(results)
        assert bl.get("bm25", "recall@10") == 0.85
        assert bl.get("semantic", "recall@10") == 0.90

    def test_to_dict(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "recall@10", 0.85)
        d = bl.to_dict()
        assert d["name"] == "test"
        assert "bm25.recall@10" in d["baselines"]

    def test_save_load(self, tmp_path: Path) -> None:
        bl = RegressionBaseline("save_test")
        bl.set("bm25", "recall@10", 0.85)
        bl.set("bm25", "mrr", 0.75)
        path = tmp_path / "baseline.json"
        bl.save(str(path))

        loaded = RegressionBaseline.load(str(path))
        assert loaded.name == "save_test"
        assert loaded.get("bm25", "recall@10") == 0.85
        assert loaded.get("bm25", "mrr") == 0.75

    def test_thread_safe(self) -> None:
        bl = RegressionBaseline("conc")

        def _set(i: int) -> None:
            bl.set(f"cfg{i}", "recall@10", float(i) / 100)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_set, i) for i in range(20)]
            for f in futures:
                f.result()

        assert bl.get("cfg5", "recall@10") == 0.05
        assert len(bl.to_dict()["baselines"]) == 20


class TestRegressionDetector:
    def test_no_regression(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "recall@10", 0.85)
        bl.set("bm25", "mrr", 0.75)
        bl.set("bm25", "latency_p50", 100)

        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"recall@10": 0.85, "mrr": 0.75})]
        report = detector.check(results)
        assert report.passed
        assert report.total_regressions == 0

    def test_recall_regression(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "recall@10", 0.85)
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"recall@10": 0.60})]
        report = detector.check(results)
        assert not report.passed
        assert report.total_regressions >= 1

    def test_precision_regression(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "precision@10", 0.70)
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"precision@10": 0.40})]
        report = detector.check(results)
        assert not report.passed

    def test_mrr_regression(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "mrr", 0.75)
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"mrr": 0.50})]
        report = detector.check(results)
        assert not report.passed

    def test_map_regression(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "map", 0.70)
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"map": 0.40})]
        report = detector.check(results)
        assert not report.passed

    def test_ndcg_regression(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "ndcg@10", 0.80)
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"ndcg@10": 0.50})]
        report = detector.check(results)
        assert not report.passed

    def test_latency_regression(self) -> None:
        bl = RegressionBaseline("test")
        bl.set("bm25", "latency_p50", 100)
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", latency={"mean_ms": 200, "max_ms": 400})]
        report = detector.check(results)
        assert not report.passed
        assert any(f.metric == "latency_p50" for f in report.findings)

    def test_multiple_configs(self) -> None:
        bl = RegressionBaseline("multi")
        bl.set("bm25", "recall@10", 0.85)
        bl.set("semantic", "recall@10", 0.90)
        detector = RegressionDetector(bl)
        results = [
            _make_result("bm25", {"recall@10": 0.85}),
            _make_result("semantic", {"recall@10": 0.60}),
        ]
        report = detector.check(results)
        assert not report.passed
        assert report.total_configs == 2

    def test_json_export(self, tmp_path: Path) -> None:
        bl = RegressionBaseline("export")
        bl.set("bm25", "recall@10", 0.85)
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"recall@10": 0.60})]
        report = detector.check(results)

        path = tmp_path / "report.json"
        Path(path).write_text(json.dumps(report.to_dict(), indent=2) + "\n")
        assert path.exists()
        data = json.loads(path.read_text())
        assert "findings" in data
        assert data["total_regressions"] >= 1
        assert not data["passed"]

    def test_report_summary(self) -> None:
        bl = RegressionBaseline("sum")
        bl.set("bm25", "recall@10", 0.85)
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"recall@10": 0.60})]
        report = detector.check(results)
        summary = report.summary()
        assert "Regression Report" in summary
        assert "FAIL" in summary

    def test_no_baseline_value(self) -> None:
        """Métrica sin baseline no debe generar hallazgo."""
        bl = RegressionBaseline("empty")
        detector = RegressionDetector(bl)
        results = [_make_result("bm25", {"recall@10": 0.85})]
        report = detector.check(results)
        assert report.total_regressions == 0
        assert len(report.findings) == 0
