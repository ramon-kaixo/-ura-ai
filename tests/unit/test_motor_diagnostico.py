"""Tests para motor/diagnostico/diagnostico.py — Diagnostico."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest import mock

import pytest

from motor.core.state import DiagnoseResult, ScanResult
from motor.diagnostico.diagnostico import Diagnostico


@pytest.fixture
def scan() -> ScanResult:
    return ScanResult(
        ok=True,
        hw_health={"ok": True, "issues": []},
        red={"exit_node_online": True},
        duplicados={},
        flapping=[],
    )


@pytest.fixture
def diag(monkeypatch, scan) -> Diagnostico:
    config = mock.Mock()
    config.data_dir = "/tmp/ura_diag_test"
    qdrant = mock.Mock()
    executor = mock.Mock()
    executor.run.return_value = SimpleNamespace(returncode=0, stdout="pid1 proc1\npid2 proc2\n", stderr="")
    d = Diagnostico(config, qdrant, executor=executor)
    monkeypatch.setattr(d.cb, "operacional", mock.Mock(return_value=True))
    monkeypatch.setattr("motor.diagnostico.correlacion.agrupar_incidentes", mock.Mock(return_value=[]))
    monkeypatch.setattr("motor.diagnostico.correlacion.resumir_incidentes", mock.Mock(return_value="resumen"))
    return d


class TestRun:
    def test_run_basico(self, diag: Diagnostico, scan: ScanResult) -> None:
        r = diag.run(scan)
        assert isinstance(r, DiagnoseResult)
        assert r.ok is True
        assert r.incidentes == []
        assert "Z" in r.timestamp

    def test_run_scan_no_ok(self, diag: Diagnostico, scan: ScanResult) -> None:
        scan.ok = False
        r = diag.run(scan)
        assert r.ok is False

    def test_run_offline(self, diag: Diagnostico, scan: ScanResult) -> None:
        diag.cb.operacional = mock.Mock(return_value=False)
        r = diag.run(scan)
        assert r.modo_offline is True

    def test_run_con_incidentes_backup(self, diag: Diagnostico, scan: ScanResult, monkeypatch) -> None:
        incidente = {"tipo": "GPU", "subtipo": "power_cap"}
        monkeypatch.setattr("motor.diagnostico.diagnostico.buscar_patrones", mock.Mock(return_value=([incidente], 100)))
        backup = mock.Mock()
        monkeypatch.setattr("motor.diagnostico.diagnostico.backup_incidente", backup)
        r = diag.run(scan)
        assert r.incidentes == [incidente]
        backup.assert_called_once_with(diag.config, incidente)

    def test_run_guarda_qdrant(self, diag: Diagnostico, scan: ScanResult, monkeypatch) -> None:
        incidente = {"tipo": "GPU", "subtipo": "power_cap"}
        monkeypatch.setattr("motor.diagnostico.diagnostico.buscar_patrones", mock.Mock(return_value=([incidente], 0)))
        diag.run(scan)
        diag.qdrant.guardar_incidente.assert_called_once()

    def test_run_sin_incidentes_no_guarda(self, diag: Diagnostico, scan: ScanResult) -> None:
        diag.run(scan)
        diag.qdrant.guardar_incidente.assert_not_called()


class TestSnapshot:
    def test_snapshot_con_configs(self, diag: Diagnostico, scan: ScanResult, tmp_path, monkeypatch) -> None:
        f = tmp_path / "opencode.json"
        f.write_bytes(b"config")
        monkeypatch.setattr("motor.diagnostico.diagnostico.RUTAS_CONFIG_OPENCODE", [str(f)])
        snap = diag._tomar_snapshot_inicial()
        assert snap["procesos"] == ["pid1 proc1", "pid2 proc2"]
        assert str(f) in snap
        assert snap[str(f)]["hash"] == hashlib.sha256(b"config").hexdigest()[:16]

    def test_snapshot_sin_configs(self, diag: Diagnostico, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("motor.diagnostico.diagnostico.RUTAS_CONFIG_OPENCODE", [str(tmp_path / "nope.json")])
        snap = diag._tomar_snapshot_inicial()
        assert "procesos" in snap

    def test_snapshot_executor_error(self, diag: Diagnostico, scan: ScanResult, monkeypatch) -> None:
        diag.executor.run.side_effect = OSError("no ps")
        snap = diag._tomar_snapshot_inicial()
        assert "procesos" not in snap


class TestExtraerTags:
    def test_tags_variados(self, diag: Diagnostico, scan: ScanResult) -> None:
        incidentes = [{"tipo": "GPU", "subtipo": "power_cap"}, {"tipo": "Disco"}]
        scan.hw_health = {"ok": False, "issues": ["gpu"]}
        scan.duplicados = {"a": 1}
        scan.flapping = ["svc"]
        scan.red = {"exit_node_online": False}
        tags = diag._extraer_tags(incidentes, scan)
        assert "GPU" in tags
        assert "power_cap" in tags
        assert "Disco" in tags
        assert "hw_issue" in tags
        assert "config_conflict" in tags
        assert "flapping" in tags
        assert "exit_node_offline" in tags

    def test_tags_minimos(self, diag: Diagnostico, scan: ScanResult) -> None:
        assert diag._extraer_tags([], scan) == []


class TestDeterminarCausas:
    def test_extrae_causas(self, diag: Diagnostico) -> None:
        corr = [{"causa_raiz": "gpu_power"}, {"sin_causa": 1}, {"causa_raiz": "disco"}]
        assert diag._determinar_causas(corr) == ["gpu_power", "disco"]

    def test_vacio(self, diag: Diagnostico) -> None:
        assert diag._determinar_causas([]) == []


class TestGuardarIncidente:
    def test_sin_incidentes(self, diag: Diagnostico, scan: ScanResult) -> None:
        r = DiagnoseResult(timestamp="t")
        diag._guardar_incidente_qdrant(r, scan)
        diag.qdrant.guardar_incidente.assert_not_called()

    def test_con_impacto(self, diag: Diagnostico, scan: ScanResult) -> None:
        r = DiagnoseResult(timestamp="t")
        r.incidentes = [{"tipo": "x"}]
        r.causas_raiz = ["c"]
        r.modo_offline = True
        scan.hw_health = {"ok": False, "issues": ["gpu"]}
        diag._guardar_incidente_qdrant(r, scan)
        incidente = diag.qdrant.guardar_incidente.call_args.args[0]
        assert incidente["impacto_memoria"][0] == 1.0
        assert incidente["impacto_memoria"][5] == 1.0
        assert incidente["impacto_memoria"][6] == 1.0
        assert incidente["tipo"] == "AutoDiagnostico"
