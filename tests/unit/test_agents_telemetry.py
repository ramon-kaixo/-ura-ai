"""Tests for core/agents/telemetry.py."""

from unittest.mock import MagicMock, patch

import pytest

from core.agents.telemetry import Telemetria


class TestCheckOllama:
    def test_con_llm_inyectado(self):
        mock_llm = MagicMock()
        mock_llm.health.return_value = {"status": "ok", "modelos_disponibles": ["a", "b"]}
        tel = Telemetria(llm=mock_llm)
        assert tel._check_ollama() == "2 modelos"

    def test_con_llm_down(self):
        mock_llm = MagicMock()
        mock_llm.health.return_value = {"status": "error"}
        tel = Telemetria(llm=mock_llm)
        assert tel._check_ollama() == "down"

    @patch("motor.core.llm.health", return_value={"status": "ok", "modelos_disponibles": ["x"]})
    def test_fallback_a_motor(self, mock_health):
        tel = Telemetria(llm=None)
        assert tel._check_ollama() == "1 modelos"
        mock_health.assert_called_once()


class TestLlmStats:
    def test_con_config(self, tmp_path, monkeypatch):
        config = tmp_path / "chunk_config.json"
        config.write_text('{"chunk_actual": 4096, "modelo": "qwen", "historico": [1, 2]}')
        monkeypatch.setattr("core.agents.telemetry.NERVIOSO", tmp_path)
        result = Telemetria.llm_stats()
        assert result["chunk_actual"] == 4096
        assert result["modelo"] == "qwen"
        assert result["historico_ajustes"] == 2

    def test_sin_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.agents.telemetry.NERVIOSO", tmp_path)
        result = Telemetria.llm_stats()
        assert result["chunk_actual"] == 8192
        assert result["modelo"] == "?"


class TestF821Count:
    @patch("core.agents.telemetry.subprocess.run")
    def test_cuenta_errores(self, mock_run):
        mock_run.return_value.stdout = "F821\nF821\nF821\n"
        result = Telemetria.f821_count()
        assert result == 3
        mock_run.assert_called_once()

    @patch("core.agents.telemetry.subprocess.run", side_effect=Exception("boom"))
    def test_error(self, mock_run):
        result = Telemetria.f821_count()
        assert result == -1


class TestReporteCompleto:
    def test_estructura(self):
        tel = Telemetria()
        with patch.object(tel, "hardware", return_value={"ram": 1000}), \
             patch.object(tel, "red", return_value={"router": "ok"}), \
             patch.object(tel, "llm_stats", return_value={"modelo": "qwen"}), \
             patch.object(tel, "f821_count", return_value=5):
            result = tel.reporte_completo()
            assert "hardware" in result
            assert "red" in result
            assert "llm" in result
            assert "f821" in result
            assert result["f821"] == 5
