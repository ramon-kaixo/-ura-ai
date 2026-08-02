"""Tests para core/cleaner/cold_refactor.py (Capa 3 — deuda tecnica y tuneladora)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "pro"))

from core.cleaner.cold_refactor import ColdRefactor, E


@pytest.fixture
def cr(monkeypatch, tmp_path) -> ColdRefactor:
    from core.cleaner import cold_refactor as mod

    monkeypatch.setattr(mod, "DQ", tmp_path / "debt_queue.json")
    monkeypatch.setattr(mod, "DH", tmp_path / "debt_history.jsonl")
    monkeypatch.setattr(mod, "RD", tmp_path / "refactor_prompts")
    monkeypatch.setattr(mod, "SD", tmp_path / "skills")
    return ColdRefactor()


class TestRegistrar:
    def test_registrar_deuda_crea_skill(self, cr: ColdRefactor, tmp_path) -> None:
        sp = cr.registrar_deuda("D1", "skill1", "codigo", ["w1"])
        assert sp.name == "skill1.py"
        assert "# DEBT_ID: D1" in sp.read_text()
        cola = json.loads((tmp_path / "debt_queue.json").read_text())
        assert cola[0]["debt_id"] == "D1"
        assert cola[0]["advertencias_originales"] == ["w1"]

    def test_registrar_limpio(self, cr: ColdRefactor, tmp_path) -> None:
        sp = cr.registrar_limpio("s2", "codigo limpio")
        assert sp.read_text() == "codigo limpio"

    def test_registrar_deuda_reemplaza_mismo_id(self, cr: ColdRefactor, tmp_path) -> None:
        cr.registrar_deuda("D1", "s1", "v1", [])
        cr.registrar_deuda("D1", "s1", "v2", [])
        cola = json.loads((tmp_path / "debt_queue.json").read_text())
        assert len(cola) == 1
        assert cola[0]["codigo_con_parche"] == "# DEBT_ID: D1\nv2"


class TestCola:
    def test_lista_vacia(self, cr: ColdRefactor) -> None:
        assert cr._l() == []

    def test_lista_corrupta(self, cr: ColdRefactor, tmp_path) -> None:
        (tmp_path / "debt_queue.json").write_text("no json")
        assert cr._l() == []

    def test_estado_deuda(self, cr: ColdRefactor) -> None:
        cr.registrar_deuda("D1", "s1", "c", [])
        e = E("D2", "s2", "p", "c2", [], "ts", resuelto=True)
        cr._a(e)
        st = cr.estado_deuda()
        assert st == {"total": 2, "pend": 1, "res": 1, "skills": ["s1"]}

    def test_timestamp_iso(self, cr: ColdRefactor) -> None:
        ts = cr._n()
        assert "T" in ts and ts.endswith("+00:00")


class TestTuneladora:
    @pytest.mark.asyncio
    async def test_sin_pendientes(self, cr: ColdRefactor) -> None:
        r = await cr.ejecutar_tuneladora()
        assert r == {"procesados": 0, "resueltos": 0, "reintentados": 0, "abandonados": 0}

    @pytest.mark.asyncio
    async def test_ref_ok_valida_y_resuelve(self, cr: ColdRefactor, monkeypatch, tmp_path) -> None:
        cr.registrar_deuda("D1", "skill1", "codigo", ["w"])

        async def fake_ref(e):
            return "codigo_limpio"

        sentinel = SimpleNamespace(ok=True, errores=[], analizar=lambda li, n: SimpleNamespace(ok=True))
        orchestrator = SimpleNamespace(ok=True, validar=mock.AsyncMock(return_value=SimpleNamespace(ok=True)))
        monkeypatch.setattr(cr, "_ref", fake_ref)
        monkeypatch.setattr("core.guardians.ast_sentinel.ASTSentinel", lambda: sentinel)
        monkeypatch.setattr("core.sandbox.docker_orchestrator.DockerOrchestrator", lambda: orchestrator)

        r = await cr.ejecutar_tuneladora()
        assert r == {"procesados": 1, "resueltos": 1, "reintentados": 0, "abandonados": 0}
        # El skill file fue escrito con codigo limpio
        assert (tmp_path / "skills" / "skill1.py").read_text() == "codigo_limpio"
        # La cola marca resuelto
        cola = json.loads((tmp_path / "debt_queue.json").read_text())
        assert cola[0]["resuelto"] is True

    @pytest.mark.asyncio
    async def test_ref_falla_reintenta(self, cr: ColdRefactor, monkeypatch) -> None:
        cr.registrar_deuda("D1", "skill1", "codigo", [])
        monkeypatch.setattr(cr, "_ref", mock.AsyncMock(return_value=None))
        r = await cr.ejecutar_tuneladora()
        assert r["reintentados"] == 1
        assert r["resueltos"] == 0

    @pytest.mark.asyncio
    async def test_sentinel_invalido_reintenta(self, cr: ColdRefactor, monkeypatch) -> None:
        cr.registrar_deuda("D1", "skill1", "codigo", [])
        monkeypatch.setattr(cr, "_ref", mock.AsyncMock(return_value="codigo_limpio"))
        sentinel = SimpleNamespace(analizar=lambda li, n: SimpleNamespace(ok=False, errores=["x"]))
        monkeypatch.setattr("core.guardians.ast_sentinel.ASTSentinel", lambda: sentinel)
        r = await cr.ejecutar_tuneladora()
        assert r["reintentados"] == 1

    @pytest.mark.asyncio
    async def test_orchestrator_invalido_reintenta(self, cr: ColdRefactor, monkeypatch) -> None:
        cr.registrar_deuda("D1", "skill1", "codigo", [])
        monkeypatch.setattr(cr, "_ref", mock.AsyncMock(return_value="codigo_limpio"))
        monkeypatch.setattr("core.guardians.ast_sentinel.ASTSentinel", lambda: SimpleNamespace(analizar=lambda li, n: SimpleNamespace(ok=True)))
        monkeypatch.setattr("core.sandbox.docker_orchestrator.DockerOrchestrator", lambda: SimpleNamespace(validar=mock.AsyncMock(return_value=SimpleNamespace(ok=False))))
        r = await cr.ejecutar_tuneladora()
        assert r["reintentados"] == 1

    @pytest.mark.asyncio
    async def test_abandonados_con_3_intentos(self, cr: ColdRefactor, monkeypatch) -> None:
        e = E("D1", "skill1", "p", "c", [], "ts", n_intentos=3)
        cr._a(e)
        r = await cr.ejecutar_tuneladora()
        assert r["procesados"] == 0
        assert r["abandonados"] == 1


class TestRef:
    @pytest.mark.asyncio
    async def test_ref_ok(self, cr: ColdRefactor, monkeypatch) -> None:
        e = E("D1", "s", "p", "codigo", ["w"], "ts")
        resp = SimpleNamespace(status_code=200, json=lambda: {"codigo_limpio": "limpio"})

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                return resp

        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: FakeClient())
        out = await cr._ref(e)
        assert out == "limpio"

    @pytest.mark.asyncio
    async def test_ref_error_http(self, cr: ColdRefactor, monkeypatch) -> None:
        e = E("D1", "s", "p", "codigo", [], "ts")
        resp = SimpleNamespace(status_code=500, json=lambda: {})

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                return resp

        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: FakeClient())
        assert await cr._ref(e) is None

    @pytest.mark.asyncio
    async def test_ref_excepcion(self, cr: ColdRefactor, monkeypatch) -> None:
        e = E("D1", "s", "p", "codigo", [], "ts")
        monkeypatch.setattr("httpx.AsyncClient", mock.Mock(side_effect=OSError("net")))
        assert await cr._ref(e) is None
