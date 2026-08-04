"""Tests para scripts/pro/auditoria_continua.py — integración con tuneladora."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from scripts.pro.auditoria_continua import (
    detectar_regresiones,
    guardar_alerta_en_memoria,
    leer_ultimo_reporte_tuneladora,
)


def _reporte(verdict="OK", cov=80.0, failed=0) -> dict:
    return {
        "episode_id": "ep-1",
        "verdict": verdict,
        "coverage": {"global": cov},
        "tests": {"failed": failed},
    }


class TestLeerUltimoReporte:
    def test_dir_no_existe(self, tmp_path: Path) -> None:
        assert leer_ultimo_reporte_tuneladora(tmp_path / "nope") is None

    def test_sin_archivos(self, tmp_path: Path) -> None:
        d = tmp_path / "reports"
        d.mkdir()
        assert leer_ultimo_reporte_tuneladora(d) is None

    def test_lee_el_mas_reciente(self, tmp_path: Path) -> None:
        d = tmp_path / "reports"
        d.mkdir()
        (d / "a.json").write_text(json.dumps({"episode_id": "viejo"}))
        (d / "b.json").write_text(json.dumps({"episode_id": "nuevo"}))
        report = leer_ultimo_reporte_tuneladora(d)
        assert report["episode_id"] == "nuevo"

    def test_json_invalido_ignorado(self, tmp_path: Path) -> None:
        d = tmp_path / "reports"
        d.mkdir()
        (d / "roto.json").write_text("{no es json")
        assert leer_ultimo_reporte_tuneladora(d) is None


class TestDetectarRegresiones:
    def test_sin_reporte_actual(self) -> None:
        alertas = detectar_regresiones(None, {})
        assert "No hay reporte" in alertas[0]

    def test_sin_reporte_anterior(self) -> None:
        alertas = detectar_regresiones(_reporte(), None)
        assert "anterior" in alertas[0]

    def test_regresion_cobertura(self) -> None:
        alertas = detectar_regresiones(_reporte(cov=70.0), _reporte(cov=85.0))
        assert any("REGRESION" in a and "70" in a for a in alertas)

    def test_sin_regresion(self) -> None:
        alertas = detectar_regresiones(_reporte(cov=90.0), _reporte(cov=80.0))
        assert alertas == []

    def test_tests_fallaron(self) -> None:
        alertas = detectar_regresiones(_reporte(failed=3), _reporte())
        assert any("3 tests fallaron" in a for a in alertas)

    def test_verdict_fail(self) -> None:
        alertas = detectar_regresiones(_reporte(verdict="FAIL"), _reporte())
        assert any("FAIL" in a for a in alertas)


class TestGuardarAlerta:
    def test_sin_alertas(self) -> None:
        assert guardar_alerta_en_memoria([]) == 0

    def test_guarda_con_store_mock(self) -> None:
        store = mock.Mock()
        n = guardar_alerta_en_memoria(["alerta1", "alerta2"], store=store)
        assert n == 2
        assert store.record.call_count == 2
        payload = store.record.call_args[0][0]
        assert payload["tipo"] == "alerta_supervisor"
        assert payload["componente"] == "auditoria_continua"

    def test_store_falla_silencioso(self) -> None:
        store = mock.Mock()
        store.record.side_effect = RuntimeError("boom")
        assert guardar_alerta_en_memoria(["a"], store=store) == 0
