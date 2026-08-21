"""Tests para scripts/pro/orquestador.py (Módulo 8)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "pro"))

from orquestador import (
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
        import orquestador as orq

        tarea = _tarea()
        with mock.patch.dict(
            orq.FASE_FUNCS,
            {"implementacion": lambda t: {"fase": "implementacion", "ok": False, "detail": "sin cambios"}},
        ):
            report = orq.ejecutar_tarea(tarea, fases=["contexto", "implementacion", "commit"])
        # implementacion falla -> para
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
            "contexto",
            "planificacion",
            "implementacion",
            "revision",
            "tests",
            "auditoria",
            "quality_gate",
            "commit",
        ]


class TestFasesSubprocess:
    def test_revision_ok(self) -> None:
        from orquestador import fase_revision

        with mock.patch("orquestador._run", return_value=mock.Mock(returncode=0, stdout="")):
            r = fase_revision(_tarea())
        assert r["ok"] is True

    def test_revision_falla(self) -> None:
        from orquestador import fase_revision

        with mock.patch("orquestador._run", return_value=mock.Mock(returncode=1, stdout="errores")):
            r = fase_revision(_tarea())
        assert r["ok"] is False

    def test_tests_ok(self) -> None:
        from orquestador import fase_tests

        with mock.patch("orquestador._run", return_value=mock.Mock(returncode=0, stdout="100 passed")):
            r = fase_tests(_tarea())
        assert r["ok"] is True

    def test_tests_fallan(self) -> None:
        from orquestador import fase_tests

        with mock.patch("orquestador._run", return_value=mock.Mock(returncode=1, stdout="2 failed")):
            r = fase_tests(_tarea())
        assert r["ok"] is False

    def test_auditoria_ok(self) -> None:
        import json as _json

        from orquestador import fase_auditoria

        with mock.patch(
            "orquestador._run",
            return_value=mock.Mock(stdout=_json.dumps({"ok": 10, "total": 10})),
        ):
            r = fase_auditoria(_tarea())
        assert r["ok"] is True
        assert "10/10" in r["detail"]

    def test_auditoria_no_json(self) -> None:
        from orquestador import fase_auditoria

        with mock.patch("orquestador._run", return_value=mock.Mock(stdout="no json")):
            r = fase_auditoria(_tarea())
        assert r["ok"] is False

    def test_quality_gate_acepta(self) -> None:
        from orquestador import fase_quality_gate

        with mock.patch("orquestador._run", return_value=mock.Mock(returncode=0, stdout="ACCEPTED")):
            r = fase_quality_gate(_tarea())
        assert r["ok"] is True

    def test_quality_gate_rechaza(self) -> None:
        from orquestador import fase_quality_gate

        with mock.patch("orquestador._run", return_value=mock.Mock(returncode=1, stdout="REJECTED")):
            r = fase_quality_gate(_tarea())
        assert r["ok"] is False
