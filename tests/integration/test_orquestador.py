"""Tests para scripts/pro/orquestador.py (Módulo 8)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "pro"))

from orquestador import (  # noqa: E402
    FASES,
    cargar_tarea,
    ejecutar_tarea,
    fase_commit,
    fase_contexto,
)


def _tarea() -> dict:
    return {"id": "T-1", "objetivo": "test", "tipo": "feature", "modulo": "motor"}


class TestCargarTarea:
    def test_valida_campos(self, tmp_path: Path) -> None:
        f = tmp_path / "t.json"
        f.write_text(json.dumps(_tarea()))
        assert cargar_tarea(f)["id"] == "T-1"

    def test_falta_campo(self, tmp_path: Path) -> None:
        f = tmp_path / "t.json"
        f.write_text('{"id": "x"}')
        with pytest.raises(ValueError):
            cargar_tarea(f)

    def test_json_invalido(self, tmp_path: Path) -> None:
        f = tmp_path / "t.json"
        f.write_text("{no json")
        with pytest.raises(json.JSONDecodeError):
            cargar_tarea(f)


class TestFases:
    def test_contexto(self) -> None:
        r = fase_contexto(_tarea())
        assert r["ok"] is True
        assert "memoria" in r["info"]

    def test_commit_skip(self) -> None:
        r = fase_commit(_tarea())
        assert r["ok"] is True
        assert "SKIP" in r["detail"]


class TestEjecutar:
    def test_para_en_fallo(self) -> None:
        tarea = _tarea()
        report = ejecutar_tarea(tarea, fases=["contexto", "implementacion", "commit"])
        # implementacion falla (sin cambios) -> para
        assert report["estado"] == "fallida"
        assert "commit" not in report["resultados"]

    def test_estado_completada(self) -> None:
        tarea = _tarea()
        report = ejecutar_tarea(tarea, fases=["contexto", "planificacion", "commit"])
        assert report["estado"] == "completada"

    def test_fase_desconocida(self) -> None:
        tarea = _tarea()
        report = ejecutar_tarea(tarea, fases=["no-existe"])
        assert report["estado"] == "fallida"

    def test_guarda_log(self, tmp_path: Path) -> None:
        import orquestador as orq

        with mock.patch("orquestador.LOGS_DIR", tmp_path / "logs"):
            orq.ejecutar_tarea(_tarea(), fases=["commit"])
        logs = list((tmp_path / "logs").glob("*.json"))
        assert len(logs) == 1

    def test_fases_orden(self) -> None:
        assert FASES == [
            "contexto", "planificacion", "implementacion",
            "revision", "tests", "auditoria", "quality_gate", "commit",
        ]
