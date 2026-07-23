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
