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
        assert store.store.call_count == 2
        episodes = [c.args[0] for c in store.store.call_args_list]
        assert all(e.tags == ["alerta_supervisor", "auditoria_continua"] for e in episodes)
        assert episodes[0].payload == "alerta1"
        assert episodes[1].payload == "alerta2"

    def test_store_falla_silencioso(self) -> None:
        store = mock.Mock()
        store.store.side_effect = RuntimeError("boom")
        assert guardar_alerta_en_memoria(["a"], store=store) == 0

    def test_store_real_guarda(self, tmp_path: Path) -> None:
        from motor.intelligence.memory.episodic import EpisodeStore, EpisodeStoreConfig

        store = EpisodeStore(EpisodeStoreConfig(persist_path=str(tmp_path / "ep.db")))
        n = guardar_alerta_en_memoria(["alerta real"], store=store)
        assert n == 1
        store2 = EpisodeStore(EpisodeStoreConfig(persist_path=str(tmp_path / "ep.db")))
        episodes = store2.get_by_time_range(
            start="2020-01-01T00:00:00", end="2100-01-01T00:00:00"
        )
        assert any("alerta real" in getattr(e, "payload", "") for e in episodes)


class TestLeerUltimoReporteN:
    def test_n_mas_reciente(self, tmp_path: Path) -> None:
        d = tmp_path / "r"
        d.mkdir()
        (d / "a.json").write_text(json.dumps({"episode_id": "a"}))
        (d / "b.json").write_text(json.dumps({"episode_id": "b"}))
        assert leer_ultimo_reporte_tuneladora(d, n=0)["episode_id"] == "b"
        assert leer_ultimo_reporte_tuneladora(d, n=1)["episode_id"] == "a"

    def test_n_fuera_de_rango(self, tmp_path: Path) -> None:
        d = tmp_path / "r"
        d.mkdir()
        (d / "a.json").write_text(json.dumps({"episode_id": "a"}))
        assert leer_ultimo_reporte_tuneladora(d, n=5) is None


class TestCheckRegresiones:
    def test_registrado_en_checks(self) -> None:
        from scripts.pro.auditoria_continua import CHECKS

        assert any(c["name"] == "Regresiones tuneladora" for c in CHECKS)

    def test_sin_reportes_ok(self, monkeypatch) -> None:
        from scripts.pro.auditoria_continua import _chequear_regresiones_tuneladora

        monkeypatch.setattr(
            "scripts.pro.auditoria_continua.leer_ultimo_reporte_tuneladora",
            lambda n=0: None,
        )
        ok, msg = _chequear_regresiones_tuneladora()
        assert ok is True
        assert "No hay reporte" in msg

    def test_con_regresion_fail(self, monkeypatch) -> None:
        from scripts.pro.auditoria_continua import _chequear_regresiones_tuneladora

        reportes = [{"verdict": "FAIL", "episode_id": "a"}, {"verdict": "OK", "episode_id": "b"}]

        def fake(n=0):
            return reportes[n] if n < len(reportes) else None

        monkeypatch.setattr(
            "scripts.pro.auditoria_continua.leer_ultimo_reporte_tuneladora",
            fake,
        )
        with mock.patch(
            "scripts.pro.auditoria_continua.guardar_alerta_en_memoria"
        ) as m_guardar:
            ok, msg = _chequear_regresiones_tuneladora()
        assert ok is False
        assert "FAIL" in msg
        m_guardar.assert_called_once()

    def test_con_regresion_cobertura(self, monkeypatch) -> None:
        from scripts.pro.auditoria_continua import _chequear_regresiones_tuneladora

        reportes = [
            {"verdict": "OK", "coverage": {"global": 60.0}},
            {"verdict": "OK", "coverage": {"global": 80.0}},
        ]

        def fake(n=0):
            return reportes[n] if n < len(reportes) else None

        monkeypatch.setattr(
            "scripts.pro.auditoria_continua.leer_ultimo_reporte_tuneladora",
            fake,
        )
        ok, msg = _chequear_regresiones_tuneladora()
        assert ok is False
        assert "REGRESION" in msg

    def test_excepcion_en_check(self, monkeypatch) -> None:
        from scripts.pro.auditoria_continua import _chequear_regresiones_tuneladora

        monkeypatch.setattr(
            "scripts.pro.auditoria_continua.leer_ultimo_reporte_tuneladora",
            mock.Mock(side_effect=RuntimeError("boom")),
        )
        ok, msg = _chequear_regresiones_tuneladora()
        assert ok is False
        assert "falló" in msg
