"""Tests de motor/scanner/__init__.py (Scanner) — cobertura 0% -> objetivo >=90%."""

from __future__ import annotations

import socket
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from motor.core.config import UraConfig
from motor.scanner import (
    DOCKER_ALIASES,
    SERVICIOS_SYSTEMD,
    Scanner,
)


def _res(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, returncode=returncode, stderr="")


@pytest.fixture
def cfg(tmp_path: Path) -> UraConfig:
    return UraConfig(data_dir=str(tmp_path), baseline_path="", is_vm=True)


class TestEsFisico:
    def test_virt_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res("none"))
        assert Scanner._es_fisico() is True

    def test_virt_kvm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res("kvm"))
        assert Scanner._es_fisico() is False

    def test_virt_falla_cpuinfo_hypervisor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("no virt")))
        with mock.patch("builtins.open", mock.mock_open(read_data="model name: foo hypervisor xyz")):
            assert Scanner._es_fisico() is False

    def test_virt_falla_cpuinfo_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("no virt")))
        with mock.patch("builtins.open", mock.mock_open(read_data="model name: foo")):
            assert Scanner._es_fisico() is True

    def test_virt_doble_falla(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("no virt")))
        monkeypatch.setattr("builtins.open", mock.Mock(side_effect=OSError("no cpuinfo")))
        assert Scanner._es_fisico() is True  # fallback default True


class TestHostname:
    def test_ok(self) -> None:
        s = Scanner(cfg_fake())
        assert s._get_hostname() == socket.gethostname()

    def test_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("socket.gethostname", mock.Mock(side_effect=OSError("sin hostname")))
        assert Scanner(cfg_fake())._get_hostname() == "unknown"


class TestCheckServicios:
    def test_systemd_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "motor.scanner._executor.run",
            lambda cmd, timeout=5: _res("active") if cmd[0] == "systemctl" and cmd[1] == "is-active" else _res("x"),
        )
        s = Scanner(cfg_fake())
        out = s._check_servicios()
        for svc in SERVICIOS_SYSTEMD:
            assert out[svc] == "active"

    def test_systemd_inactive_sin_unit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(cmd, timeout=5):
            if cmd[0] == "systemctl" and cmd[1] == "is-active":
                return _res("inactive")
            if cmd[0] == "systemctl" and cmd[1] == "list-units":
                return _res("")  # no existe la unit
            return _res("")

        monkeypatch.setattr("motor.scanner._executor.run", fake_run)
        s = Scanner(cfg_fake())
        out = s._check_servicios()
        assert all(out[svc] == "not_found" for svc in SERVICIOS_SYSTEMD)

    def test_systemd_inactive_con_unit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(cmd, timeout=5):
            if cmd[0] == "systemctl" and cmd[1] == "is-active":
                return _res("inactive")
            return _res("sshd.service")

        monkeypatch.setattr("motor.scanner._executor.run", fake_run)
        s = Scanner(cfg_fake())
        out = s._check_servicios()
        assert out["sshd"] == "inactive"  # unit existe -> estado real

    def test_file_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(cmd, timeout=5):
            raise FileNotFoundError(cmd[0])

        monkeypatch.setattr("motor.scanner._executor.run", fake_run)
        s = Scanner(cfg_fake())
        out = s._check_servicios()
        assert all(out[svc] == "not_found" for svc in SERVICIOS_SYSTEMD)

    def test_error_generico(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("boom")))
        s = Scanner(cfg_fake())
        out = s._check_servicios()
        assert all(out[svc] == "unknown" for svc in SERVICIOS_SYSTEMD)

    def test_docker_aliases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        docker_out = "\n".join(
            [
                f"{DOCKER_ALIASES['vane']}\trunning",
                f"{DOCKER_ALIASES['agent-search']}\trunning",
                "qdrant\trunning",
                "n8n\texited",
            ]
        )

        def fake_run(cmd, timeout=5):
            if cmd[0] == "docker":
                return _res(docker_out)
            return _res("active")

        monkeypatch.setattr("motor.scanner._executor.run", fake_run)
        s = Scanner(cfg_fake())
        out = s._check_servicios()
        assert out["vane"] == "active"
        assert out["agent-search"] == "active"
        assert out["qdrant"] == "active"  # running -> active
        assert out["n8n"] == "exited"
        assert out["searxng"] == "not_found"


class TestUnitExists:
    def test_existe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res("sshd.service"))
        assert Scanner(cfg_fake())._unit_exists("sshd") is True

    def test_no_existe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res(""))
        assert Scanner(cfg_fake())._unit_exists("x") is False

    def test_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("boom")))
        assert Scanner(cfg_fake())._unit_exists("x") is False


class TestListDocker:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "motor.scanner._executor.run", lambda *a, **k: _res("c1\trunning\nc2\texited")
        )
        out = Scanner(cfg_fake())._list_docker_containers()
        assert out == {"c1": "running", "c2": "exited"}

    def test_lineas_sin_tab(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res("c1\trunning\nbasura"))
        out = Scanner(cfg_fake())._list_docker_containers()
        assert out == {"c1": "running"}

    def test_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("boom")))
        assert Scanner(cfg_fake())._list_docker_containers() == {}


class TestCheckRecursos:
    def test_psutil(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.scanner as scanner_mod

        monkeypatch.setattr(
            scanner_mod, "_recursos_psutil", lambda: {"ram_pct": 50, "disk_pct": 60, "zombies": 0}
        )
        assert Scanner(cfg_fake())._check_recursos()["ram_pct"] == 50

    def test_proc_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "_recursos_psutil", lambda: None)
        monkeypatch.setattr(scanner_mod, "_recursos_proc", lambda: {"ram_pct": 10, "disk_pct": 20, "zombies": 1})
        out = Scanner(cfg_fake())._check_recursos()
        assert out["zombies"] == 1


class TestCheckContenedores:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "motor.scanner._executor.run", lambda *a, **k: _res("c1\trunning\nc2\texited\nc3\trunning")
        )
        out = Scanner(cfg_fake())._check_contenedores()
        assert out == {"total": 3, "running": 2, "exited": 1}

    def test_linea_vacia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res("c1\trunning\n\n"))
        out = Scanner(cfg_fake())._check_contenedores()
        assert out["total"] == 1

    def test_linea_tab_sola(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res("\t"))
        out = Scanner(cfg_fake())._check_contenedores()
        assert out["total"] == 0  # len(parts) != 2

    def test_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("boom")))
        out = Scanner(cfg_fake())._check_contenedores()
        assert out == {"total": 0, "running": 0, "exited": 0}


class TestDetectarCambios:
    def test_primera_vez(self) -> None:
        s = Scanner(cfg_fake())
        r = SimpleNamespace(
            servicios={"a": "active"},
            recursos={"ram_pct": 50},
            contenedores={"total": 1},
            hw_health={"ok": True},
        )
        assert s._detectar_cambios(r) == (0, [])
        assert s._ventana_previa["servicios"] == {"a": "active"}

    def test_segunda_vez_diff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        s = Scanner(cfg_fake())
        r1 = SimpleNamespace(
            servicios={"a": "active"}, recursos={"ram_pct": 50}, contenedores={"total": 1}, hw_health={"ok": True}
        )
        s._detectar_cambios(r1)
        r2 = SimpleNamespace(
            servicios={"a": "failed"}, recursos={"ram_pct": 50}, contenedores={"total": 1}, hw_health={"ok": True}
        )
        with mock.patch("motor.scanner.compute_diff", return_value=(2, ["cambio"])) as m:
            diff, anom = s._detectar_cambios(r2)
        m.assert_called_once()
        assert diff == 2 and anom == ["cambio"]
        assert s._ventana_previa["servicios"] == {"a": "failed"}


class TestCalcularHealthScore:
    def _r(self, **kw) -> SimpleNamespace:
        base = {
            "servicios": {"a": "active", "b": "ok"},
            "recursos": {"ram_pct": 50, "disk_pct": 50, "zombies": 0},
            "red": {"latencia_ms": 0},
            "flapping": [],
            "hw_health": {"ok": True},
            "diff_total": 0,
        }
        base.update(kw)
        return SimpleNamespace(**base)

    def test_perfecto(self) -> None:
        assert Scanner(cfg_fake())._calcular_health_score(self._r()) == 100.0

    def test_servicios_fallados(self) -> None:
        s = Scanner(cfg_fake())
        r = self._r(servicios={"a": "failed", "b": "failed", "c": "degraded"})
        assert s._calcular_health_score(r) == 100 - 30

    def test_ram_alta(self) -> None:
        s = Scanner(cfg_fake())
        assert s._calcular_health_score(self._r(recursos={"ram_pct": 95, "disk_pct": 50, "zombies": 0})) == 85.0
        assert s._calcular_health_score(self._r(recursos={"ram_pct": 85, "disk_pct": 50, "zombies": 0})) == 90.0

    def test_disk_alta(self) -> None:
        s = Scanner(cfg_fake())
        assert s._calcular_health_score(self._r(recursos={"ram_pct": 50, "disk_pct": 95, "zombies": 0})) == 85.0
        assert s._calcular_health_score(self._r(recursos={"ram_pct": 50, "disk_pct": 85, "zombies": 0})) == 90.0

    def test_zombies_latencia_flapping_hw_diff(self) -> None:
        s = Scanner(cfg_fake())
        r = self._r(
            recursos={"ram_pct": 50, "disk_pct": 50, "zombies": 2},
            red={"latencia_ms": 100},  # 100/20 = 5
            flapping=["a"],
            hw_health={"ok": False},
            diff_total=3,
        )
        assert s._calcular_health_score(r) == 100 - 10 - 5 - 5 - 15 - 6

    def test_minimo_0(self) -> None:
        s = Scanner(cfg_fake())
        r = self._r(
            servicios={f"s{i}": "failed" for i in range(20)},
            recursos={"ram_pct": 95, "disk_pct": 95, "zombies": 3},
            red={"latencia_ms": 500},
            flapping=["x", "y", "z", "w", "v"],
            hw_health={"ok": False},
            diff_total=50,
        )
        assert s._calcular_health_score(r) == 0.0


class TestDetectarDuplicados:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "motor.scanner._executor.run",
            lambda *a, **k: _res("opencode serve\nopencode serve\nnode x\nnode x\nbash\n"),
        )
        out = Scanner(cfg_fake())._detectar_duplicados()
        assert out["procesos"]["opencode serve"] == 2
        assert out["procesos"]["node x"] == 2

    def test_sin_duplicados(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res("bash\npython x\n"))
        assert Scanner(cfg_fake())._detectar_duplicados() == {}

    def test_args_vacios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", lambda *a, **k: _res("\n   \n"))
        assert Scanner(cfg_fake())._detectar_duplicados() == {}

    def test_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("boom")))
        assert Scanner(cfg_fake())._detectar_duplicados() == {}


class TestSnapshotHash:
    def test_archivos_inexistentes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner.RUTAS_CONFIG_OPENCODE", ["/no/existe/1.jsonc", "/no/existe/2.json"])
        h = Scanner(cfg_fake())._tomar_snapshot_hash()
        assert len(h) == 16

    def test_archivos_existentes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f1 = tmp_path / "a.jsonc"
        f2 = tmp_path / "b.json"
        f1.write_text("{}")
        f2.write_text("{}")
        monkeypatch.setattr("motor.scanner.RUTAS_CONFIG_OPENCODE", [str(f1), str(f2)])
        h = Scanner(cfg_fake())._tomar_snapshot_hash()
        assert len(h) == 16
        f2.write_text("{\"x\": 1}")
        h2 = Scanner(cfg_fake())._tomar_snapshot_hash()
        assert h2 != h


class TestDetectarOrphans:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.scanner as scanner_mod

        for fn in ("_detectar_pid_files", "_detectar_hijos_huerfanos", "_detectar_docker_dangling", "_detectar_systemd_failed"):
            monkeypatch.setattr(scanner_mod, fn, lambda *a, **k: None)
        s = Scanner(cfg_fake())
        s._detectar_orphans()  # no lanza
        assert True

    def test_acumula(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.scanner as scanner_mod

        def add(orphans, *a, **k):
            orphans.append({"tipo": "x"})

        for fn in ("_detectar_pid_files", "_detectar_hijos_huerfanos", "_detectar_docker_dangling", "_detectar_systemd_failed"):
            monkeypatch.setattr(scanner_mod, fn, add)
        s = Scanner(cfg_fake())
        assert len(s._detectar_orphans()) == 4


class TestDetectarSystemdFailed:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "motor.scanner._executor.run",
            lambda *a, **k: _res("foo.service failed\n● bar.service failed\n"),
        )
        out = Scanner(cfg_fake())._detectar_systemd_failed()
        assert "foo.service" in out
        assert "bar.service" in out

    def test_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("motor.scanner._executor.run", mock.Mock(side_effect=OSError("boom")))
        assert Scanner(cfg_fake())._detectar_systemd_failed() == []


class TestRun:
    @pytest.fixture
    def s(self, cfg: UraConfig) -> Scanner:
        sc = Scanner(cfg)
        sc.sliding.add_and_check = mock.Mock(return_value=[])
        return sc

    def test_run_vm(self, s: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        s.cal._baseline = {}
        for method in (
            "_get_hostname",
            "_check_servicios",
            "_check_recursos",
            "_check_contenedores",
            "_list_docker_containers",
            "_detectar_cambios",
            "_detectar_duplicados",
            "_detectar_orphans",
            "_detectar_systemd_failed",
            "_tomar_snapshot_hash",
        ):
            monkeypatch.setattr(s, method, mock.Mock(return_value={} if not method.startswith("_detectar_cambios") else (0, [])))
        monkeypatch.setattr(s, "_es_fisico", lambda: False)
        monkeypatch.setattr(s, "_calcular_health_score", lambda r: 77.0)
        monkeypatch.setattr("motor.scanner.escanear_red", lambda config: {"latencia_ms": 5})
        monkeypatch.setattr("motor.scanner.escanear_hw_vm", lambda: {"ok": True})
        r = s.run()
        assert r.ok is True
        assert r.health_score == 77.0
        assert r.hw_health == {"ok": True}
        assert r.calibration_status == "learning"

    def test_run_fisico(self, s: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        for method in (
            "_get_hostname",
            "_check_servicios",
            "_check_recursos",
            "_check_contenedores",
            "_list_docker_containers",
            "_detectar_cambios",
            "_detectar_duplicados",
            "_detectar_orphans",
            "_detectar_systemd_failed",
            "_tomar_snapshot_hash",
        ):
            monkeypatch.setattr(s, method, mock.Mock(return_value={} if not method.startswith("_detectar_cambios") else (0, [])))
        monkeypatch.setattr(s, "_es_fisico", lambda: True)
        monkeypatch.setattr(s, "_calcular_health_score", lambda r: 90.0)
        monkeypatch.setattr("motor.scanner.escanear_red", lambda config: {"latencia_ms": 5})
        monkeypatch.setattr("motor.scanner.escanear_asus", lambda config: {"temp_gpu": 45})
        monkeypatch.setattr("motor.scanner.escanear_hw_asus", lambda temp_gpu: {"ok": True, "temp": temp_gpu})
        r = s.run()
        assert r.ok is True
        assert r.hw_health["temp"] == 45

    def test_run_calibracion_activa(self, s: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        for method in (
            "_get_hostname",
            "_check_servicios",
            "_check_recursos",
            "_check_contenedores",
            "_list_docker_containers",
            "_detectar_cambios",
            "_detectar_duplicados",
            "_detectar_orphans",
            "_detectar_systemd_failed",
            "_tomar_snapshot_hash",
        ):
            monkeypatch.setattr(s, method, mock.Mock(return_value={} if not method.startswith("_detectar_cambios") else (0, [])))
        monkeypatch.setattr(s, "_es_fisico", lambda: True)
        monkeypatch.setattr(s, "_calcular_health_score", lambda r: 50.0)
        s.cal._baseline = {"ram_pct_max": 90}
        monkeypatch.setattr(s.cal, "detectar_anomalias", lambda r: ["anomalia"], raising=False)
        monkeypatch.setattr("motor.scanner.escanear_red", lambda config: {"latencia_ms": 5})
        monkeypatch.setattr("motor.scanner.escanear_asus", lambda config: {"temp_gpu": 40})
        monkeypatch.setattr("motor.scanner.escanear_hw_asus", lambda temp_gpu: {"ok": True})
        r = s.run()
        assert r.calibration_status == "active"
        assert "anomalia" in r.anomalias


def cfg_fake() -> UraConfig:
    return UraConfig(data_dir="/tmp/ura-test", baseline_path="", is_vm=True)
