"""Tests de cobertura de motor/pipeline/orchestrator.py (Orchestrator)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

from motor.core.state import DiagnoseResult, PipelineResult, PreflightResult, ScanResult, VerifyResult
from motor.pipeline.orchestrator import (
    ARCHIVO_DIAGNOSTICO,
    ARCHIVO_ESTADO,
    ARCHIVO_TRENDS,
    Orchestrator,
)


class _Config:
    deploy_dir = ""

    def __init__(self, deploy_dir: str) -> None:
        self.deploy_dir = deploy_dir


def _scan(**kw) -> ScanResult:
    base = {
        "ok": True,
        "timestamp": "2026-08-18T00:00:00+00:00",
        "hostname": "test-host",
        "health_score": 95.0,
        "diff_total": 0,
        "recursos": {"ram_pct": 40, "disk_pct": 30, "load_1m": 0.5},
        "servicios": {},
        "red": {},
        "hw_health": {"ok": True, "issues": []},
        "orphans": [],
        "systemd_failed": [],
    }
    base.update(kw)
    return ScanResult(**base)


def _pipe(scan: ScanResult | None = None, diagnose: DiagnoseResult | None = None) -> PipelineResult:
    return PipelineResult(
        scan=scan or _scan(),
        diagnose=diagnose or DiagnoseResult(),
        verify=VerifyResult(ok=True),
    )


def _mk(monkeypatch, tmp_path, *, preflight=None, scan=None, diagnose=None, verify=None):
    cfg = _Config(str(tmp_path))
    def _preflight(cfg_):
        return preflight if preflight is not None else PreflightResult()

    monkeypatch.setattr("motor.pipeline.orchestrator.ejecutar_preflight", _preflight)
    monkeypatch.setattr(
        "motor.pipeline.orchestrator.Scanner",
        lambda c: SimpleNamespace(run=lambda: scan if scan is not None else _scan()),
    )
    monkeypatch.setattr(
        "motor.pipeline.orchestrator.Diagnostico",
        lambda c, q: SimpleNamespace(run=lambda s: diagnose if diagnose is not None else DiagnoseResult()),
    )
    monkeypatch.setattr(
        "motor.pipeline.orchestrator.ejecutar_verificacion",
        lambda c, hubo_cambios=False: verify if verify is not None else VerifyResult(ok=True),
    )
    monkeypatch.setattr(
        "motor.pipeline.orchestrator.QdrantClient", SimpleNamespace(instancia=lambda c: mock.Mock())
    )
    return Orchestrator(cfg)


class TestRun:
    def test_preflight_bloqueado(self, monkeypatch, tmp_path) -> None:
        orch = _mk(monkeypatch, tmp_path, preflight=PreflightResult(ok=False, bloqueado=True, razon="no git"))
        res = orch.run()
        assert not res.ok
        assert "Preflight bloqueado" in res.error

    def test_dry_run(self, monkeypatch, tmp_path, capsys) -> None:
        orch = _mk(monkeypatch, tmp_path)
        res = orch.run(dry_run=True)
        assert res.ok
        assert res.scan is None

    def test_flujo_completo(self, monkeypatch, tmp_path) -> None:
        orch = _mk(monkeypatch, tmp_path, diagnose=DiagnoseResult(incidentes=[], causas_raiz=[]))
        res = orch.run()
        assert res.ok
        assert res.verify is not None
        assert res.scan is not None
        assert (tmp_path / ARCHIVO_ESTADO).exists()
        assert (tmp_path / ARCHIVO_DIAGNOSTICO).exists()
        assert (tmp_path / ARCHIVO_TRENDS).exists()
        line = json.loads((tmp_path / ARCHIVO_TRENDS).read_text().strip().split("\n")[0])
        assert line["hostname"] == "test-host"
        assert "perf" in line

    def test_alertas_health_baja(self, monkeypatch, tmp_path, caplog) -> None:
        orch = _mk(monkeypatch, tmp_path, scan=_scan(health_score=85.0))
        with caplog.at_level("ERROR", logger="ura.alerta"):
            orch.run()
        assert any("ALERTA health=85.0" in r.message for r in caplog.records)

    def test_alertas_incidentes(self, monkeypatch, tmp_path, caplog) -> None:
        orch = _mk(monkeypatch, tmp_path, diagnose=DiagnoseResult(incidentes=[{"id": 1}]))
        with caplog.at_level("ERROR", logger="ura.alerta"):
            orch.run()
        assert any("incidentes=1" in r.message for r in caplog.records)

    def test_excepcion_interna(self, monkeypatch, tmp_path) -> None:
        cfg = _Config(str(tmp_path))

        def _boom() -> None:
            raise RuntimeError("scan exploded")

        monkeypatch.setattr("motor.pipeline.orchestrator.Scanner", lambda c: SimpleNamespace(run=_boom))
        monkeypatch.setattr(
            "motor.pipeline.orchestrator.ejecutar_preflight", lambda c: PreflightResult()
        )
        monkeypatch.setattr(
            "motor.pipeline.orchestrator.QdrantClient", SimpleNamespace(instancia=lambda c: mock.Mock())
        )
        orch = Orchestrator(cfg)
        res = orch.run()
        assert not res.ok
        assert res.error == "scan exploded"


class TestSideEffects:
    def test_registrar_trend_sin_scan(self, monkeypatch, tmp_path) -> None:
        orch = _mk(monkeypatch, tmp_path)
        orch._registrar_trend(PipelineResult())
        assert not (tmp_path / ARCHIVO_TRENDS).exists()

    def test_registrar_trend_sin_perf(self, monkeypatch, tmp_path) -> None:
        orch = _mk(monkeypatch, tmp_path)
        orch._registrar_trend(_pipe())
        entry = json.loads((tmp_path / ARCHIVO_TRENDS).read_text())
        assert "perf" not in entry

    def test_escribir_sin_scan_ni_diagnose(self, monkeypatch, tmp_path) -> None:
        orch = _mk(monkeypatch, tmp_path)
        orch._escribir_side_effects(PipelineResult())
        assert not (tmp_path / ARCHIVO_ESTADO).exists()

    def test_escribir_con_diagnose_sin_scan(self, monkeypatch, tmp_path) -> None:
        orch = _mk(monkeypatch, tmp_path)
        orch._escribir_side_effects(PipelineResult(diagnose=DiagnoseResult(ok=True)))
        assert (tmp_path / ARCHIVO_DIAGNOSTICO).exists()
        assert not (tmp_path / ARCHIVO_ESTADO).exists()


class TestEmit:
    def test_emit_no_lanza(self, monkeypatch, tmp_path) -> None:
        # _emit documenta emision JSON a stdout pero el cuerpo esta vacio
        # (hallazgo registrado; nadie consume el stdout del orquestador).
        orch = _mk(monkeypatch, tmp_path)
        orch._emit(PipelineResult(ok=True, timestamp="ts"))
