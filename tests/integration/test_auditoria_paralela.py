"""Tests para scripts/pro/auditoria_paralela.py (10 checks)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "pro"))

from scripts.pro.auditoria_paralela import (
    check_duplicados,
    check_imports_circulares,
    check_lock_stale,
    check_memorias,
    check_quality_gate,
    check_rendimiento,
    check_secretos,
    check_supervisor,
    run_all,
)


@pytest.mark.slow
class TestChecks:
    def test_memorias(self) -> None:
        r = check_memorias()
        assert isinstance(r["ok"], bool)
        assert "check" in r

    def test_supervisor(self) -> None:
        r = check_supervisor()
        assert isinstance(r["ok"], bool)

    def test_quality_gate(self) -> None:
        r = check_quality_gate()
        assert r["ok"] is True
        assert r["detail"] == "verdict=ACCEPTED"

    def test_lock_stale(self) -> None:
        r = check_lock_stale()
        assert r["ok"] is True

    def test_imports_circulares(self) -> None:
        r = check_imports_circulares()
        assert r["ok"] is True

    def test_secretos(self) -> None:
        r = check_secretos()
        assert isinstance(r["ok"], bool)
        assert "hallazgos" in r["detail"]

    def test_rendimiento(self) -> None:
        r = check_rendimiento()
        assert r["ok"] is True

    def test_duplicados_estructura(self) -> None:
        r = check_duplicados()
        assert isinstance(r["ok"], bool)
        assert "ADR-220" in r["detail"]

    def test_run_all_estructura(self) -> None:
        report = run_all()
        assert report["total"] == 10
        assert len(report["results"]) == 10
        assert 0 <= report["ok"] <= 10

    def test_check_devuelve_dict(self) -> None:
        from scripts.pro.auditoria_paralela import _check

        r = _check("x", True, "detalle")
        assert r == {"check": "x", "ok": True, "detail": "detalle"}

    def test_main_retorna_codigo(self) -> None:
        import auditoria_paralela as ap

        with mock.patch("sys.argv", ["auditoria_paralela.py", "--json"]), mock.patch.object(
            ap, "run_all",
            return_value={"ok": 10, "total": 10, "results": [{"check": "x", "ok": True, "detail": ""}] * 10},
        ):
            code = ap.main()
        assert code == 0
