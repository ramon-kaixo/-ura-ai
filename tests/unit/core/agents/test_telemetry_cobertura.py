#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/agents/telemetry.py."""

import pytest
import json
import tempfile
import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock, mock_open
from datetime import UTC, datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.agents.telemetry import Telemetria


class TestTelemetriaInit:
    @pytest.mark.unit
    def test_init_sin_llm(self):
        telemetria = Telemetria()
        assert telemetria._llm is None

    @pytest.mark.unit
    def test_init_con_llm(self):
        mock_llm = MagicMock()
        telemetria = Telemetria(llm=mock_llm)
        assert telemetria._llm is mock_llm


class TestTelemetriaCheckOllama:
    @pytest.mark.unit
    def test_check_ollama_con_llm_ok(self):
        mock_llm = MagicMock()
        mock_llm.health.return_value = {"status": "ok", "modelos_disponibles": ["model1", "model2"]}
        telemetria = Telemetria(llm=mock_llm)
        assert telemetria._check_ollama() == "2 modelos"

    @pytest.mark.unit
    def test_check_ollama_con_llm_sin_modelos(self):
        mock_llm = MagicMock()
        mock_llm.health.return_value = {"status": "ok", "modelos_disponibles": []}
        telemetria = Telemetria(llm=mock_llm)
        assert telemetria._check_ollama() == "0 modelos"

    @pytest.mark.unit
    def test_check_ollama_con_llm_status_no_ok(self):
        mock_llm = MagicMock()
        mock_llm.health.return_value = {"status": "error"}
        telemetria = Telemetria(llm=mock_llm)
        assert telemetria._check_ollama() == "down"

    @pytest.mark.unit
    def test_check_ollama_sin_llm_ok(self):
        with patch('motor.core.llm.health') as mock_health:
            mock_health.return_value = {"status": "ok", "modelos_disponibles": ["model1"]}
            telemetria = Telemetria()
            assert telemetria._check_ollama() == "1 modelos"

    @pytest.mark.unit
    def test_check_ollama_sin_llm_status_no_ok(self):
        with patch('motor.core.llm.health') as mock_health:
            mock_health.return_value = {"status": "error"}
            telemetria = Telemetria()
            assert telemetria._check_ollama() == "down"


class TestTelemetriaHardware:
    @pytest.mark.unit
    def test_hardware_returns_dict_with_timestamp(self):
        """Verifica que hardware() retorna dict con timestamp."""
        from motor.core.agents.telemetry import Telemetria
        resultado = Telemetria.hardware()
        assert isinstance(resultado, dict)
        assert "timestamp" in resultado

    @pytest.mark.unit
    def test_hardware_contains_expected_keys(self):
        """Verifica que contiene las claves esperadas."""
        from motor.core.agents.telemetry import Telemetria
        resultado = Telemetria.hardware()
        # Al menos estas claves deben existir
        assert "ram_total_mb" in resultado
        assert "ram_libre_mb" in resultado
        assert "ram_pct" in resultado
        assert "cpu_pct" in resultado

    @pytest.mark.unit
    def test_hardware_ram_values_positive(self):
        """Verifica que valores de RAM son positivos."""
        from motor.core.agents.telemetry import Telemetria
        resultado = Telemetria.hardware()
        assert resultado["ram_total_mb"] >= 0
        assert resultado["ram_libre_mb"] >= 0
        assert 0 <= resultado["ram_pct"] <= 100
        assert resultado["cpu_pct"] >= 0


class TestTelemetriaRed:
    @pytest.mark.unit
    def test_red_model_router_ok(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        with patch('httpx.get', return_value=mock_response), \
             patch.object(Telemetria, '_check_ollama', return_value="2 modelos"):
            telemetria = Telemetria()
            assert telemetria.red()["model_router"] == "ok"

    @pytest.mark.unit
    def test_red_model_router_down(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch('httpx.get', return_value=mock_response), \
             patch.object(Telemetria, '_check_ollama', return_value="2 modelos"):
            telemetria = Telemetria()
            assert telemetria.red()["model_router"] == "down"

    @pytest.mark.unit
    def test_red_model_router_exception(self):
        with patch('httpx.get', side_effect=Exception("connection error")), \
             patch.object(Telemetria, '_check_ollama', return_value="2 modelos"):
            telemetria = Telemetria()
            assert telemetria.red()["model_router"] == "down"

    @pytest.mark.unit
    def test_red_ollama_check(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        with patch('httpx.get', return_value=mock_response), \
             patch.object(Telemetria, '_check_ollama', return_value="3 modelos") as mock_check:
            telemetria = Telemetria()
            assert telemetria.red()["ollama"] == "3 modelos"


class TestTelemetriaLLMStats:
    @pytest.mark.unit
    def test_llm_stats_archivo_existe(self, tmp_path):
        config_file = tmp_path / "chunk_config.json"
        config_file.write_text(json.dumps({
            "chunk_actual": 4096, "modelo": "qwen3.6:27b", "historico": [1, 2, 3]
        }))
        with patch('motor.core.agents.telemetry.NERVIOSO', tmp_path):
            from motor.core.agents.telemetry import Telemetria
            resultado = Telemetria.llm_stats()
            assert resultado == {"chunk_actual": 4096, "modelo": "qwen3.6:27b", "historico_ajustes": 3}

    @pytest.mark.unit
    def test_llm_stats_archivo_no_existe(self):
        with patch('motor.core.agents.telemetry.NERVIOSO', Path("/fake")):
            from motor.core.agents.telemetry import Telemetria
            assert Telemetria.llm_stats() == {"chunk_actual": 8192, "modelo": "?", "historico_ajustes": 0}

    @pytest.mark.unit
    def test_llm_stats_json_invalido(self, tmp_path):
        config_file = tmp_path / "chunk_config.json"
        config_file.write_text("no es json")
        with patch('motor.core.agents.telemetry.NERVIOSO', tmp_path):
            from motor.core.agents.telemetry import Telemetria
            try:
                Telemetria.llm_stats()
            except json.JSONDecodeError:
                pass


class TestTelemetriaF821Count:
    @pytest.mark.unit
    def test_f821_count_exitoso(self):
        with patch('motor.core.agents.telemetry.subprocess.run') as mock_run, \
             patch('motor.core.agents.telemetry.RUFF', "ruff"), \
             patch('motor.core.agents.telemetry.URA_ROOT', Path("/fake")):
            mock_run.return_value = MagicMock(stdout="file.py:1:1: F821\nfile.py:2:1: F821\nfile.py:3:1: E501")
            from motor.core.agents.telemetry import Telemetria
            assert Telemetria.f821_count() == 2

    @pytest.mark.unit
    def test_f821_count_error(self):
        with patch('motor.core.agents.telemetry.subprocess.run', side_effect=Exception("error")):
            from motor.core.agents.telemetry import Telemetria
            assert Telemetria.f821_count() == -1


class TestTelemetriaReporteCompleto:
    @pytest.mark.unit
    def test_reporte_completo_estructura(self):
        with patch.object(Telemetria, 'hardware', return_value={"ram_pct": 50}), \
             patch.object(Telemetria, 'red', return_value={"model_router": "ok"}), \
             patch.object(Telemetria, 'llm_stats', return_value={"modelo": "test"}), \
             patch.object(Telemetria, 'f821_count', return_value=0):
            telemetria = Telemetria()
            reporte = telemetria.reporte_completo()
            assert "hardware" in reporte
            assert "red" in reporte
            assert "llm" in reporte
            assert "f821" in reporte
            assert reporte["hardware"]["ram_pct"] == 50


class TestTelemetriaShadowHealth:
    @pytest.mark.unit
    def test_on_layer_start(self, caplog):
        telemetria = Telemetria()
        with caplog.at_level(logging.DEBUG):
            telemetria.on_layer_start(1, "test_layer")
        assert "Shadow Health layer 1 (test_layer) starting" in caplog.text

    @pytest.mark.unit
    def test_on_layer_end(self, caplog):
        telemetria = Telemetria()
        with caplog.at_level(logging.INFO):
            telemetria.on_layer_end(2, "test_layer", "ok", 150.5)
        assert "Shadow Health layer 2 (test_layer): ok in 150ms" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
