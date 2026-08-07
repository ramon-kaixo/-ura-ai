"""Tests para tuneladora PipelineEngine (scripts/pro/tuneladora/engine.py)."""
from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.engine import PipelineEngine, PromotionPolicy


@pytest.fixture
def engine() -> PipelineEngine:
    return PipelineEngine()


@pytest.fixture
def mock_subprocess() -> mock.Mock:
    with mock.patch("subprocess.run") as m:
        m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
        yield m


class TestPromotionPolicy:
    def test_initially_not_promotable(self):
        policy = PromotionPolicy(mock.Mock())
        assert policy.can_promote is False

    def test_record_makes_promotable(self):
        policy = PromotionPolicy(mock.Mock())
        policy.record("test", True, "OK")
        assert policy.can_promote is True

    def test_fail_prevents_promotion(self):
        policy = PromotionPolicy(mock.Mock())
        policy.record("test", False, "FAIL")
        assert policy.can_promote is False

    def test_mixed_results_block_promotion(self):
        policy = PromotionPolicy(mock.Mock())
        policy.record("a", True)
        policy.record("b", False)
        assert policy.can_promote is False

    def test_budget_within_limits(self):
        policy = PromotionPolicy(mock.Mock())
        policy.set_budget(50, 5000)
        assert policy.check_budget(30, 1000) is True

    def test_budget_exceeded(self):
        policy = PromotionPolicy(mock.Mock())
        policy.set_budget(50, 5000)
        assert policy.check_budget(100, 10000) is False


class TestEngineInit:
    def test_engine_creates_with_defaults(self):
        eng = PipelineEngine()
        assert eng.config is not None
        assert eng.log is not None
        assert eng.ledger is not None
        assert eng.checkpoint is not None
        assert eng.promotion is not None

    def test_engine_accepts_custom_config(self):
        config = Configuration()
        eng = PipelineEngine(config=config, pipeline="test")
        assert eng.config is config


class TestRunScript:
    def test_run_script_success(self, engine, mock_subprocess):
        result = engine.run_script("test_script.py", ["--arg"], timeout=10)
        assert result.returncode == 0
        mock_subprocess.assert_called_once()

    def test_run_script_args_default_none(self, engine):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            engine.run_script("test.py")
            args = m.call_args[0][0]
            assert args[-1] == "test.py"

    def test_run_script_timeout(self, engine):
        with mock.patch("subprocess.run") as m:
            m.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)
            with pytest.raises(subprocess.TimeoutExpired):
                engine.run_script("test.py", timeout=1)


class TestRunRuff:
    def test_run_ruff_calls_ruff(self, engine):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            engine.run_ruff(["check", "."])
            args = m.call_args[0][0]
            assert "ruff" in args[0] or args[0].endswith("ruff")


class TestRunGit:
    def test_run_git_calls_git(self, engine):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="abc123", stderr="")
            result = engine.run_git(["rev-parse", "HEAD"])
            assert result.returncode == 0
            args = m.call_args[0][0]
            assert args[0] == "git"
            assert "rev-parse" in args


class TestHealth:
    def test_health_ollama_returns_list(self, engine):
        with mock.patch("httpx.get") as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {"models": [{"name": "llama3"}]}
            models = engine.health_ollama()
            assert isinstance(models, list)
            assert len(models) == 1

    def test_health_ollama_fallback_empty(self, engine):
        with mock.patch("httpx.get") as m:
            m.side_effect = Exception("connection failed")
            models = engine.health_ollama()
            assert models == []

    def test_health_disk_returns_dict(self, engine):
        with mock.patch("os.statvfs") as m:
            class FakeStat:
                f_frsize = 4096
                f_bavail = 1000000

            m.return_value = FakeStat()
            result = engine.health_disk()
            assert isinstance(result, dict)
            assert "libre_gb" in result
            assert result["libre_gb"] > 0


class TestReport:
    def test_report_logs_data(self, engine):
        with mock.patch.object(engine.log, "report") as m:
            engine.report("Test Report", {"key": "value"})
            m.assert_called_once()


class TestPromotionPolicyExtra:
    def test_budget_set_y_check(self):
        policy = PromotionPolicy(mock.Mock())
        policy.set_budget(max_files=10, max_lines=100)
        assert policy.check_budget(5, 50) is True
        assert policy.check_budget(11, 50) is False
        assert policy.check_budget(5, 101) is False

    def test_summary_agrupa(self):
        policy = PromotionPolicy(mock.Mock())
        policy.record("test", True, "OK")
        policy.record("test", False, "FAIL")
        policy.record("ruff", True, "OK")
        lines = policy.summary
        assert any("test" in l for l in lines)
        assert len(lines) >= 2


class TestRunScriptExtra:
    def test_dry_run_devuelve_simulado(self, engine):
        engine.set_dry_run(True)
        with mock.patch.object(engine.ledger, "add_warning") as m_warn:
            result = engine.run_script("scripts/pro/x.py", args=["--json"])
        assert result.returncode == 0
        assert result.stdout == "[dry run]"
        m_warn.assert_called_once()

    def test_script_falla_notifica(self, engine):
        with mock.patch("subprocess.run") as m_run, mock.patch.object(engine, "notify") as m_notify:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="boom")
            engine.run_script("scripts/pro/x.py")
        m_notify.assert_called_once()
        assert "boom" in m_notify.call_args[0][2]

    def test_run_ruff_error_loguea_stderr(self, engine):
        with mock.patch("subprocess.run") as m_run, mock.patch.object(engine.log, "warning") as m_warn:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="err")
            engine.run_ruff(["check", "."])
        m_warn.assert_called_once()


class TestRunPlugins:
    def test_secuencial(self, engine):
        def fn_a():
            return "a"

        def fn_b():
            return "b"

        results = engine.run_plugins([("a", fn_a), ("b", fn_b)], parallel=False)
        assert results == {"a": "a", "b": "b"}

    def test_secuencial_con_error(self, engine):
        def fn_boom():
            raise RuntimeError("x")

        results = engine.run_plugins([("boom", fn_boom)], parallel=False)
        assert "error" in results["boom"]

    def test_paralelo(self, engine):
        results = engine.run_plugins([("a", lambda: 1), ("b", lambda: 2)], parallel=True)
        assert results["a"] == 1
        assert results["b"] == 2

    def test_paralelo_con_error(self, engine):
        def fn_boom():
            raise RuntimeError("x")

        results = engine.run_plugins([("boom", fn_boom)], parallel=True)
        assert "error" in results["boom"]

    def test_un_solo_plugin_no_lanza_thread(self, engine):
        results = engine.run_plugins([("a", lambda: "solo")], parallel=True)
        assert results == {"a": "solo"}


class TestNotify:
    def test_sin_alert_engine_loguea(self, engine):
        engine._alert_engine = None
        with mock.patch.object(engine.log, "warning") as m_warn:
            engine.notify("warning", "Titulo", "Desc")
        m_warn.assert_called_once()

    def test_con_alert_engine_guarda(self, engine):
        engine._alert_engine = mock.Mock()
        engine._alert_engine._alert_history = []
        engine.notify("critical", "T", "D")
        assert len(engine._alert_engine._alert_history) == 1
        assert engine._alert_engine._alert_history[0].severity == "critical"


class TestHealthExtra:
    def test_health_ollama_ok(self, engine):

        resp = mock.Mock()
        resp.status_code = 200
        resp.json.return_value = {"models": [{"name": "qwen"}]}
        with mock.patch("httpx.get", return_value=resp) as m_get:
            models = engine.health_ollama()
        assert models == [{"name": "qwen"}]
        m_get.assert_called_once()

    def test_health_disk_critico_notifica(self, engine):
        with mock.patch("os.statvfs") as m, mock.patch.object(engine, "notify") as m_notify:
            class FakeStat:
                f_frsize = 4096
                f_bavail = 1000

            m.return_value = FakeStat()
            result = engine.health_disk()
        assert result["libre_gb"] < 10
        m_notify.assert_called_once()

    def test_health_disk_error(self, engine):
        with mock.patch("os.statvfs", side_effect=OSError("x")):
            assert engine.health_disk() == {"libre_gb": 0}

    def test_health_git_ok(self, engine):
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            result = engine.health_git()
        assert result == {"ok": True, "changes": 0}

    def test_health_git_sucio_notifica(self, engine):
        out = "\n".join(f" M file{i}.py" for i in range(12))
        with mock.patch("subprocess.run") as m_run, mock.patch.object(engine, "notify") as m_notify:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=out, stderr="")
            result = engine.health_git()
        assert result["ok"] is False
        assert result["changes"] == 12
        m_notify.assert_called_once()

    def test_health_git_no_repo(self, engine):
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="")
            result = engine.health_git()
        assert result["ok"] is False
        assert "No es un repo" in result["error"]

    def test_health_tests_ok(self, engine):
        stdout = "12 passed, 0 failed, 0 errors in 2s"
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
            result = engine.health_tests(target="tests/unit")
        assert result["ok"] is True
        assert result["passed"] == 12

    def test_health_tests_fail(self, engine):
        stdout = "3 passed, 2 failed, 1 error in 2s"
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout, stderr="")
            result = engine.health_tests()
        assert result["ok"] is False
        assert result["failed"] == 2
        assert result["errors"] == 1

    def test_health_tests_wildcard_sin_match(self, engine):
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            result = engine.health_tests(target="no-existe-*.py")
        assert result["ok"] is False
        assert "No files match" in result["error"]

    def test_health_ruff_ok(self, engine):
        with mock.patch.object(engine, "run_ruff") as m_ruff:
            m_ruff.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="All checks passed!", stderr="")
            result = engine.health_ruff()
        assert result["ok"] is True
        assert result["errors"] == 0

    def test_health_ruff_con_errores(self, engine):
        with mock.patch.object(engine, "run_ruff") as m_ruff:
            m_ruff.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="a.py:1:1 X\nb.py:2:2 Y\n", stderr="")
            result = engine.health_ruff()
        assert result["ok"] is False
        assert result["errors"] == 2

    def test_health_bandit_ok(self, engine):
        stdout = "Issue: X\nSeverity: Low\n\nCode scanned"
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
            result = engine.health_bandit()
        assert result["ok"] is True
        assert result["low"] == 1

    def test_health_bandit_medium_bloquea(self, engine):
        stdout = "Severity: Medium\nSeverity: High"
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
            result = engine.health_bandit()
        assert result["ok"] is False
        assert result["medium"] == 1
        assert result["high"] == 1

    def test_parse_count(self, engine):
        assert engine._parse_count("5 passed", "passed") == 5
        assert engine._parse_count("nada", "passed") == 0
