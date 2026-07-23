"""Tests para plugins de tuneladora (scripts/pro/tuneladora/plugins/)."""
from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.arq_check import ARQCheckPlugin
from scripts.pro.tuneladora.plugins.cleanup import CleanupPlugin
from scripts.pro.tuneladora.plugins.code_quality import CodeQualityPlugin
from scripts.pro.tuneladora.plugins.health import HealthPlugin
from scripts.pro.tuneladora.plugins.reporting import ReportingPlugin


@pytest.fixture
def engine() -> PipelineEngine:
    return PipelineEngine()


@pytest.fixture
def code_quality(engine: PipelineEngine) -> CodeQualityPlugin:
    return CodeQualityPlugin(engine)


class TestCodeQualityPlugin:
    def test_ruff_check_returns_dict(self, code_quality):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="F821:5 F841:3", stderr="")
            result = code_quality.ruff_check()
            assert isinstance(result, dict)
            assert "f821" in result
            assert "f841" in result

    def test_ruff_check_parses_stdout(self, code_quality):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="file.py:1: F821 undefined name", stderr="")
            result = code_quality.ruff_check()
            assert result["f821"] >= 1

    def test_ruff_fix_calls_subprocess(self, code_quality):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            result = code_quality.ruff_fix()
            assert isinstance(result, dict)
            m.assert_called_once()

    def test_ruff_format_calls_subprocess(self, code_quality):
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            result = code_quality.ruff_format()
            assert isinstance(result, dict)
            m.assert_called_once()


class TestHealthPlugin:
    def test_check_all_returns_dict(self, engine):
        plugin = HealthPlugin(engine)
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="Mem: 100 50 50", stderr="")
            with mock.patch.object(engine, "health_disk") as hd:
                hd.return_value = {"libre_gb": 100}
                with mock.patch.object(engine, "health_ollama") as ho:
                    ho.return_value = [{"name": "llama3"}]
                    result = plugin.check_all()
                    assert isinstance(result, dict)
                    assert "disco" in result
                    assert "ollama" in result
                    assert "ram_usada_mb" in result

    def test_check_all_fallback_on_error(self, engine):
        plugin = HealthPlugin(engine)
        with mock.patch("subprocess.run") as m:
            m.side_effect = Exception("fail")
            with mock.patch.object(engine, "health_disk") as hd:
                hd.return_value = {"libre_gb": 0}
                with mock.patch.object(engine, "health_ollama") as ho:
                    ho.return_value = []
                    result = plugin.check_all()
                    assert isinstance(result, dict)
                    assert "zombies" in result
                    assert result["zombies"] == -1


class TestCleanupPlugin:
    def test_watermark_returns_dict(self, engine):
        plugin = CleanupPlugin(engine)
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout='"score": 85', stderr="")
            result = plugin.watermark()
            assert isinstance(result, dict)

    def test_forense_aislamientos_no_dir(self, engine):
        plugin = CleanupPlugin(engine)
        with mock.patch("pathlib.Path.exists") as m:
            m.return_value = False
            result = plugin.forense_aislamientos()
            assert isinstance(result, dict)

    def test_conciencia_returns_dict(self, engine):
        plugin = CleanupPlugin(engine)
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr="")
            result = plugin.conciencia()
            assert isinstance(result, dict)


class TestARQCheckPlugin:
    def test_check_returns_dict(self, engine):
        plugin = ARQCheckPlugin(engine)
        engine.promotion.record = mock.Mock()
        with mock.patch("subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout='{"blocks": {"test": [{"level": "WARNING"}]}}',
                stderr="",
            )
            result = plugin.check()
            assert isinstance(result, dict)
            assert "status" in result
            assert "total_warn" in result

    def test_check_timeout(self, engine):
        plugin = ARQCheckPlugin(engine)
        with mock.patch("subprocess.run") as m:
            m.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=120)
            result = plugin.check()
            assert result["status"] == "error"
            assert "timeout" in result["detail"].lower()


class TestReportingPlugin:
    def test_save_maintenance_state(self, engine, tmp_path):
        plugin = ReportingPlugin(engine)
        # Mock config.nervioso to use tmp_path
        engine.config.nervioso = tmp_path
        plugin.save_maintenance_state({"result": "ok"}, "ligero")
        state_file = tmp_path / "estado_mantenimiento.json"
        assert state_file.exists()
