"""Tests for core/mochila/cost_tracker.py."""

import json

import pytest

from core.mochila.cost_tracker import CostTracker


@pytest.fixture
def tracker(tmp_path):
    return CostTracker(tarifas={"ollama": 0.0, "gemini": 0.002}, cost_file=tmp_path / "costs.jsonl")


class TestRegistrar:
    def test_escribe_entrada(self, tracker, tmp_path):
        entry = tracker.registrar("gemini", "gemini-pro", 100, 50)
        assert entry["prompt_tokens"] == 100
        assert entry["completion_tokens"] == 50
        assert entry["total_tokens"] == 150
        lineas = (tmp_path / "costs.jsonl").read_text().splitlines()
        assert len(lineas) == 1

    def test_coste_calculado(self, tracker):
        entry = tracker.registrar("gemini", "m", 100, 100)
        assert entry["cost_estimate"] == 0.4  # 200 * 0.002

    def test_coste_cero_ollama(self, tracker):
        entry = tracker.registrar("ollama", "llama", 1000, 1000)
        assert entry["cost_estimate"] == 0.0

    def test_provider_desconocido_gratis(self, tracker):
        entry = tracker.registrar("otro", "m", 10, 10)
        assert entry["cost_estimate"] == 0.0

    def test_timestamp_y_fecha(self, tracker):
        entry = tracker.registrar("ollama", "m", 1, 1)
        assert isinstance(entry["timestamp"], float)
        assert len(entry["date"]) == 10


class TestCalcularCoste:
    def test_formula(self, tracker):
        assert tracker._calcular_coste("gemini", 250, 250) == 1.0

    def test_cero_tokens(self, tracker):
        assert tracker._calcular_coste("gemini", 0, 0) == 0.0


class TestResumenHoy:
    def test_sin_archivo(self, tracker, tmp_path):
        tracker._cost_file = tmp_path / "inexistente.jsonl"
        res = tracker.resumen_hoy()
        assert res["total_cost"] == 0.0
        assert res["total_tokens"] == 0
        assert res["por_provider"] == {}

    def test_acumula_del_dia(self, tracker):
        tracker.registrar("gemini", "m", 100, 100)  # cost 0.4
        tracker.registrar("gemini", "m", 50, 50)  # cost 0.2
        tracker.registrar("ollama", "ll", 10, 10)  # cost 0
        res = tracker.resumen_hoy()
        assert res["total_cost"] == 0.6
        assert res["total_tokens"] == 320
        assert res["por_provider"]["gemini"] == 2
        assert res["por_provider"]["ollama"] == 1

    def test_ignora_lineas_rojas(self, tracker, tmp_path):
        (tmp_path / "costs.jsonl").write_text("{mal\n\n" + json.dumps({"date": "2000-01-01"}) + "\n")
        res = tracker.resumen_hoy()
        assert res["total_cost"] == 0.0

    def test_redondea(self, tracker):
        tracker.tarifas["gemini"] = 0.000001
        tracker.registrar("gemini", "m", 111, 111)
        res = tracker.resumen_hoy()
        assert isinstance(res["total_cost"], float)
