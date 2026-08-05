"""Tests para scripts/pro/quality_gate.py (del otro agente — coexiste con auditoria_continua)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from scripts.pro.quality_gate import _parse_reporte, evaluar, leer_ultimo_reporte


class TestParseReporte:
    def test_formato_runner(self, tmp_path: Path) -> None:
        f = tmp_path / "r.json"
        f.write_text(json.dumps({"verdict": "OK", "mode": "check", "files": ["a.py"], "telemetry": {}}))
        data = _parse_reporte(f)
        assert data["verdict"] == "OK"
        assert data["files"] == ["a.py"]

    def test_formato_snapshot(self, tmp_path: Path) -> None:
        f = tmp_path / "meta.json"
        f.write_text(json.dumps({"created": "2026-01-01", "label": "ciclo", "files": []}))
        data = _parse_reporte(f)
        assert data["verdict"] == "SNAPSHOT"
        assert data["mode"] == "ciclo"


class TestEvaluar:
    def test_reporte_ok_acepta(self) -> None:
        verdict, alertas = evaluar({"verdict": "OK", "telemetry": {}})
        assert verdict == "ACCEPTED"
        assert alertas == []

    def test_reporte_real_sin_cobertura_acepta(self) -> None:
        # El reporte real del runner no trae coverage — no debe rechazar
        reporte = {
            "verdict": "OK",
            "telemetry": {"head": "abc", "duration_s": 5.0, "n_files": 2},
        }
        verdict, alertas = evaluar(reporte)
        assert verdict == "ACCEPTED"
        assert alertas == []

    def test_verdict_fail_rechaza(self) -> None:
        verdict, alertas = evaluar({"verdict": "FAIL", "telemetry": {}})
        assert verdict == "REJECTED"
        assert "PIPELINE FALLADO" in alertas

    def test_cobertura_baja_rechaza(self) -> None:
        verdict, alertas = evaluar({"verdict": "OK", "telemetry": {"coverage": 40.0}})
        assert verdict == "REJECTED"
        assert any("COBERTURA" in a for a in alertas)

    def test_tests_fallados_rechaza(self) -> None:
        verdict, alertas = evaluar({"verdict": "OK", "telemetry": {"tests_failed": 3}})
        assert verdict == "REJECTED"
        assert any("TESTS FALLADOS" in a for a in alertas)


class TestLeerUltimo:
    def test_sin_reportes(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert leer_ultimo_reporte() is None

    def test_lee_el_ultimo(self, tmp_path: Path, monkeypatch) -> None:
        d = tmp_path / "data" / "tuneladora_reports"
        d.mkdir(parents=True)
        (d / "a.json").write_text(json.dumps({"verdict": "OK", "telemetry": {}}))
        monkeypatch.chdir(tmp_path)
        reporte = leer_ultimo_reporte()
        assert reporte["verdict"] == "OK"


class TestEvaluarNuevoFormato:
    def test_coverage_a_nivel_raiz(self) -> None:
        # El reporte del runner ahora incluye coverage a nivel raiz
        reporte = {"verdict": "OK", "coverage": {"global": 40.0}}
        verdict, alertas = evaluar(reporte)
        assert verdict == "REJECTED"
        assert any("COBERTURA" in a for a in alertas)

    def test_tests_failed_a_nivel_raiz(self) -> None:
        reporte = {"verdict": "OK", "coverage": {"tests_failed": 3}}
        verdict, alertas = evaluar(reporte)
        assert verdict == "REJECTED"

    def test_formato_antiguo_telemetry(self) -> None:
        reporte = {"verdict": "OK", "telemetry": {"coverage": 50.0, "tests_failed": 1}}
        verdict, alertas = evaluar(reporte)
        assert verdict == "REJECTED"


class TestFailSafe:
    def test_coverage_cero_no_rechaza(self) -> None:
        # Sin datos de coverage (0) el gate NO debe bloquear
        reporte = {"verdict": "OK", "coverage": {"global": 0}}
        verdict, alertas = evaluar(reporte)
        assert verdict == "ACCEPTED"
        assert alertas == []

    def test_coverage_ausente_no_rechaza(self) -> None:
        reporte = {"verdict": "OK"}
        verdict, alertas = evaluar(reporte)
        assert verdict == "ACCEPTED"

    def test_coverage_real_bajo_rechaza(self) -> None:
        reporte = {"verdict": "OK", "coverage": {"global": 50.0}}
        verdict, alertas = evaluar(reporte)
        assert verdict == "REJECTED"


class TestModoCheck:
    def test_qg_omite_coverage_en_modo_check(self) -> None:
        # Reproduce B-21: coverage 0.6% en modo check NO debe rechazar
        reporte = {"verdict": "OK", "mode": "check", "coverage": {"global": 0.6}}
        verdict, alertas = evaluar(reporte)
        assert verdict == "ACCEPTED"

    def test_qg_aplica_coverage_en_modo_full(self) -> None:
        reporte = {"verdict": "OK", "mode": "full", "coverage": {"global": 0.6}}
        verdict, alertas = evaluar(reporte)
        assert verdict == "REJECTED"

    def test_qg_sin_mode_aplica_coverage(self) -> None:
        # Sin campo mode, se aplica el threshold (comportamiento previo)
        reporte = {"verdict": "OK", "coverage": {"global": 50.0}}
        verdict, _ = evaluar(reporte)
        assert verdict == "REJECTED"
