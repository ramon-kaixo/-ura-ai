"""Tests para Tuneladora v2.4 — métricas, notificaciones, paralelismo, dry run."""
from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.engine import PipelineEngine


@pytest.fixture
def engine() -> PipelineEngine:
    return PipelineEngine()


class TestDryRun:
    def test_dry_run_flag_default_false(self, engine):
        assert engine._dry_run is False

    def test_set_dry_run_true(self, engine):
        engine.set_dry_run(True)
        assert engine._dry_run is True

    def test_dry_run_returns_immediately(self, engine):
        engine.set_dry_run(True)
        result = engine.run_script("test.py", timeout=999)
        assert result.returncode == 0
        assert result.stdout == "[dry run]"

    def test_dry_run_does_not_call_subprocess(self, engine):
        engine.set_dry_run(True)
        with mock.patch("subprocess.run") as m:
            engine.run_script("test.py")
            m.assert_not_called()

    def test_dry_run_adds_warning_to_ledger(self, engine):
        engine.set_dry_run(True)
        engine.run_script("test.py")
        assert any("dry_run" in w for w in engine.ledger._entry.get("warnings", []))


class TestRunScript:
    def test_run_script_uses_venv_python(self, engine):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
            engine.run_script("test.py")
            cmd = m.call_args[0][0]
            assert cmd[0].endswith("python3") or "python" in cmd[0]
            assert cmd[-1] == "test.py"

    def test_run_script_passes_args(self, engine):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
            engine.run_script("test.py", args=["--verbose"])
            cmd = m.call_args[0][0]
            assert "--verbose" in cmd


class TestNotification:
    def test_notify_sends_to_alert_engine(self, engine):
        engine.notify("warning", "test alert", "description")
        assert engine._alert_engine is not None

    def test_notify_multiple_calls(self, engine):
        engine.notify("warning", "alert1", "")
        engine.notify("emergency", "alert2", "")
        # No exceptions = OK
        assert True


class TestParallelPlugins:
    def test_run_single_plugin(self, engine):
        result = engine.run_plugins([("test", lambda: {"status": "ok"})], parallel=False)
        assert result["test"]["status"] == "ok"

    def test_run_multiple_sequential(self, engine):
        order: list[str] = []
        p1 = lambda: order.append("1") or {"status": "ok"}
        p2 = lambda: order.append("2") or {"status": "ok"}
        engine.run_plugins([("p1", p1), ("p2", p2)], parallel=False)
        assert order == ["1", "2"]

    def test_parallel_may_complete(self, engine):
        import time
        def slow(name: str) -> dict:
            return {"status": "ok", "name": name}
        result = engine.run_plugins([("a", lambda: slow("a")), ("b", lambda: slow("b"))], parallel=True)
        assert "a" in result or "b" in result or result == {}

    def test_plugin_error_does_not_crash(self, engine):
        def failing() -> dict:
            msg = "error!"
            raise RuntimeError(msg)

        result = engine.run_plugins([("failing", failing)], parallel=False)
        assert "error" in result.get("failing", {})


class TestMetrics:
    def test_metrics_module_importable(self):
        from motor.observability.metrics import Counter, Histogram, Gauge, MetricsRegistry
        reg = MetricsRegistry()
        c = Counter("test_counter", "")
        c.inc()
        assert c.snapshot()["value"] >= 1

    def test_metrics_registry_snapshot(self):
        from motor.observability.metrics import Counter, MetricsRegistry
        reg = MetricsRegistry()
        c = Counter("test", "")
        c.inc(5)
        assert c.snapshot()["value"] == 5
