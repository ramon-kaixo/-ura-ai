"""Tests para motor/scanner/scanner.py — escáner principal del sistema."""

from pathlib import Path
from unittest import mock

import pytest

from motor.core.executor import ProcessResult
from motor.core.state import ScanResult
from motor.scanner import scanner
from motor.scanner.scanner import Scanner


def _res(stdout: str = "", returncode: int = 0, stderr: str = "") -> ProcessResult:
    return ProcessResult(ok=returncode == 0, cmd=[], returncode=returncode,
                         stdout=stdout, stderr=stderr)


class FakeExecutor:
    def __init__(self, default: str = "") -> None:
        self.default = default
        self.outputs: dict[str, str] = {}
        self.calls: list[list[str]] = []

    def run(self, cmd, timeout: int = 30, cwd=None, env=None) -> ProcessResult:
        self.calls.append(list(cmd))
        for key, out in self.outputs.items():
            if any(key in c for c in cmd):
                return _res(stdout=out)
        return _res(stdout=self.default)


@pytest.fixture
def config() -> mock.Mock:
    cfg = mock.Mock()
    cfg.is_vm = False
    return cfg


@pytest.fixture
def executor() -> FakeExecutor:
    return FakeExecutor()


@pytest.fixture
def sc(config: mock.Mock, executor: FakeExecutor) -> Scanner:
    with mock.patch("motor.scanner.scanner.SlidingWindow", return_value=mock.Mock()), \
            mock.patch("motor.scanner.scanner.Calibration", return_value=mock.Mock()):
        s = Scanner(config, executor=executor)
    return s


class TestEsFisico:
    def test_detect_virt_none(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.default = "none\n"
        assert sc._es_fisico() is True

    def test_detect_virt_kvm(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.default = "kvm\n"
        assert sc._es_fisico() is False

    def test_excepcion_cpuinfo(self, sc: Scanner, executor: FakeExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr("builtins.open", mock.mock_open(read_data="bare metal cpu"))
        assert sc._es_fisico() is True

    def test_excepcion_total(self, sc: Scanner, executor: FakeExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr("builtins.open", mock.Mock(side_effect=OSError("ro")))
        assert sc._es_fisico() is True


class TestRun:
    def test_run_completo_fisico(self, sc: Scanner, executor: FakeExecutor,
                                 config: mock.Mock, monkeypatch: pytest.MonkeyPatch) -> None:
        executor.default = "none\n"
        executor.outputs["docker"] = "a\tb\nc\trunning\n"
        monkeypatch.setattr(scanner, "escanear_red", mock.Mock(return_value={"latencia_ms": 10}))
        monkeypatch.setattr(scanner, "escanear_asus", mock.Mock(return_value={"temp_gpu": 50}))
        monkeypatch.setattr(scanner, "escanear_hw_asus", mock.Mock(return_value={"ok": True}))
        sc.sliding.add_and_check.return_value = []
        sc.cal.hay_baseline = False
        monkeypatch.setattr(scanner, "_detectar_pid_files", mock.Mock())
        monkeypatch.setattr(scanner, "_detectar_hijos_huerfanos", mock.Mock())
        monkeypatch.setattr(scanner, "_detectar_docker_dangling", mock.Mock())
        monkeypatch.setattr(scanner, "_detectar_systemd_failed", mock.Mock())
        monkeypatch.setattr(sc, "_tomar_snapshot_hash", mock.Mock(return_value="abc"))
        r = sc.run()
        assert r.ok is True
        assert r.snapshot_hash == "abc"
        assert r.calibration_status == "learning"

    def test_run_vm(self, sc: Scanner, executor: FakeExecutor,
                    config: mock.Mock, monkeypatch: pytest.MonkeyPatch) -> None:
        config.is_vm = True
        sc._es_fisico = mock.Mock(return_value=False)
        monkeypatch.setattr(scanner, "escanear_hw_vm", mock.Mock(return_value={"ok": True}))
        monkeypatch.setattr(scanner, "escanear_red", mock.Mock(return_value={}))
        sc.sliding.add_and_check.return_value = []
        sc.cal.hay_baseline = True
        sc.cal.detectar_anomalias.return_value = ["a1"]
        monkeypatch.setattr(scanner, "_detectar_pid_files", mock.Mock())
        monkeypatch.setattr(scanner, "_detectar_hijos_huerfanos", mock.Mock())
        monkeypatch.setattr(scanner, "_detectar_docker_dangling", mock.Mock())
        monkeypatch.setattr(scanner, "_detectar_systemd_failed", mock.Mock())
        r = sc.run()
        assert r.ok is True
        assert r.calibration_status == "active"
        assert r.anomalias == ["a1"]
        sc.cal.detectar_anomalias.assert_called_once_with(r)


class TestHostname:
    def test_ok(self, sc: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket
        monkeypatch.setattr(socket, "gethostname", mock.Mock(return_value="host-x"))
        assert sc._get_hostname() == "host-x"

    def test_falla(self, sc: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scanner.socket if hasattr(scanner, "socket") else __import__("socket"),
                            "gethostname", mock.Mock(side_effect=OSError("x")))
        import socket
        monkeypatch.setattr(socket, "gethostname", mock.Mock(side_effect=OSError("x")))
        with mock.patch.object(scanner, "log"):
            assert sc._get_hostname() == "unknown"


class TestCheckServicios:
    def test_systemd_y_docker(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.outputs["is-active"] = "active\n"
        executor.outputs["list-units"] = "sshd.service loaded active running\n"
        executor.outputs["docker"] = "qdrant\trunning\nn8n\texited\nvane\tnot_found\n"
        s = sc._check_servicios()
        assert s["sshd"] == "active"
        assert s["qdrant"] == "active"
        assert s["n8n"] == "exited"
        assert s["searxng"] == "not_found"
        assert s["vane"] == "not_found"

    def test_inactive_sin_unit(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.outputs["is-active"] = "inactive\n"
        executor.outputs["list-units"] = ""
        s = sc._check_servicios()
        assert s["sshd"] == "not_found"

    def test_file_not_found(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=FileNotFoundError("no"))
        s = sc._check_servicios()
        assert s["sshd"] == "not_found"

    def test_excepcion(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("x"))
        s = sc._check_servicios()
        assert s["sshd"] == "unknown"


class TestUnitExists:
    def test_existe(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.default = "sshd.service loaded\n"
        assert sc._unit_exists("sshd") is True

    def test_no_existe(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.default = ""
        assert sc._unit_exists("sshd") is False

    def test_excepcion(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("x"))
        assert sc._unit_exists("sshd") is False


class TestDockerContainers:
    def test_ok(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.outputs["docker"] = "a\trunning\nb\texited\n"
        assert sc._list_docker_containers() == {"a": "running", "b": "exited"}

    def test_excepcion(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("x"))
        assert sc._list_docker_containers() == {}


class TestCheckRecursos:
    def test_psutil(self, sc: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_psutil = mock.Mock()
        fake_psutil.virtual_memory.return_value = mock.Mock(percent=50.0, total=1e9, available=5e8)
        fake_psutil.disk_usage.return_value = mock.Mock(percent=40.0, total=2e9, free=1e9)
        fake_psutil.getloadavg.return_value = (0.5, 0.4, 0.3)
        fake_psutil.cpu_count.return_value = 4
        fake_psutil.process_iter.return_value = [mock.Mock(status=mock.Mock(return_value="zombie")),
                                                 mock.Mock(status=mock.Mock(return_value="running"))]
        monkeypatch.setitem(scanner.sys.modules if hasattr(scanner, "sys") else __import__("sys").modules,
                            "psutil", fake_psutil)
        import sys
        monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
        r = sc._check_recursos()
        assert r["ram_pct"] == 50.0
        assert r["zombies"] == 1

    def test_fallback_proc(self, sc: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scanner, "_recursos_psutil", mock.Mock(return_value=None))
        monkeypatch.setattr(scanner, "_recursos_proc", mock.Mock(return_value={"ram_pct": 60}))
        assert sc._check_recursos() == {"ram_pct": 60}


class TestCheckContenedores:
    def test_ok(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.outputs["docker"] = "a\trunning\nb\texited\n\n"
        c = sc._check_contenedores()
        assert c == {"total": 2, "running": 1, "exited": 1}

    def test_excepcion(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("x"))
        assert sc._check_contenedores() == {"total": 0, "running": 0, "exited": 0}


class TestDetectarCambios:
    def test_primera_vez(self, sc: Scanner) -> None:
        r = ScanResult(timestamp="t", servicios={"a": "b"}, recursos={}, contenedores={}, hw_health={})
        assert sc._detectar_cambios(r) == (0, [])
        assert sc._ventana_previa["servicios"] == {"a": "b"}

    def test_segunda_vez(self, sc: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        r = ScanResult(timestamp="t", servicios={"a": "b"}, recursos={}, contenedores={}, hw_health={})
        sc._detectar_cambios(r)
        monkeypatch.setattr(scanner, "compute_diff", mock.Mock(return_value=(3, ["an"])))
        assert sc._detectar_cambios(r) == (3, ["an"])


class TestHealthScore:
    def test_lleno(self, sc: Scanner) -> None:
        r = ScanResult(
            timestamp="t",
            servicios={"a": "failed", "b": "active"},
            recursos={"ram_pct": 95, "disk_pct": 95, "zombies": 2},
            red={"latencia_ms": 100},
            flapping=["x", "y"],
            hw_health={"ok": False},
            diff_total=3,
        )
        assert sc._calcular_health_score(r) == 14.0

    def test_sano(self, sc: Scanner) -> None:
        r = ScanResult(
            timestamp="t",
            servicios={"a": "active"},
            recursos={"ram_pct": 50, "disk_pct": 50, "zombies": 0},
            red={"latencia_ms": 10},
            flapping=[],
            hw_health={"ok": True},
            diff_total=0,
        )
        assert sc._calcular_health_score(r) == 99.5

    def test_medios(self, sc: Scanner) -> None:
        r = ScanResult(
            timestamp="t",
            servicios={"a": "not_found"},
            recursos={"ram_pct": 85, "disk_pct": 85, "zombies": 0},
            red={"latencia_ms": 0},
            flapping=[],
            hw_health={"ok": True},
            diff_total=1,
        )
        score = sc._calcular_health_score(r)
        assert 70 <= score <= 90


class TestDuplicados:
    def test_con_dups(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.outputs["ps"] = "opencode --serve\nopencode --serve\nnode x\n"
        d = sc._detectar_duplicados()
        assert "procesos" in d
        assert d["procesos"]["opencode --serve"] == 2

    def test_excepcion(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("x"))
        assert sc._detectar_duplicados() == {}


class TestSnapshotHash:
    def test_sin_archivos(self, sc: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.open", mock.Mock(side_effect=OSError("no")))
        assert len(sc._tomar_snapshot_hash()) == 16

    def test_con_archivos(self, sc: Scanner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.open", mock.mock_open(read_data=b"data"))
        assert len(sc._tomar_snapshot_hash()) == 16


class TestDetectarOrphans:
    def test_todos(self, sc: Scanner, executor: FakeExecutor) -> None:
        with mock.patch("motor.scanner.scanner._detectar_pid_files") as pid, \
                mock.patch("motor.scanner.scanner._detectar_hijos_huerfanos") as hijos, \
                mock.patch("motor.scanner.scanner._detectar_docker_dangling") as docker, \
                mock.patch("motor.scanner.scanner._detectar_systemd_failed") as sysd:
            assert sc._detectar_orphans() == []
        pid.assert_called_once()
        hijos.assert_called_once()
        docker.assert_called_once()
        sysd.assert_called_once()


class TestSystemdFailed:
    def test_ok(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.default = "● ura-x.service   loaded failed failed\nura-y.service loaded failed\n"
        assert sc._detectar_systemd_failed() == ["ura-x.service", "ura-y.service"]

    def test_excepcion(self, sc: Scanner, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("x"))
        assert sc._detectar_systemd_failed() == []


class TestRecursosProc:
    def test_proc_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scanner, "_leer_meminfo", mock.Mock(return_value=(2_000_000_000, 1_000_000_000)))
        monkeypatch.setattr(scanner, "_leer_loadavg", mock.Mock(return_value=0.5))
        monkeypatch.setattr(scanner, "_leer_statvfs", mock.Mock(return_value=(1e9, 5e8, 50.0)))
        monkeypatch.setattr(scanner, "_contar_zombies_proc", mock.Mock(return_value=3))
        r = scanner._recursos_proc()
        assert r["ram_pct"] == 50.0
        assert r["zombies"] == 3
        assert r["load_1m"] == 0.5
        assert r["ncpu"] >= 1

    def test_meminfo_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.open", mock.Mock(side_effect=OSError("ro")))
        assert scanner._leer_meminfo() == (1024, 0)

    def test_loadavg_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.open", mock.mock_open(read_data="0.75 0.50 0.25 1/2 3"))
        assert scanner._leer_loadavg() == 0.75

    def test_loadavg_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.open", mock.Mock(side_effect=OSError("ro")))
        with mock.patch.object(scanner.log, "debug"):
            assert scanner._leer_loadavg() == 0.0

    def test_meminfo_valores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        content = "MemTotal: 1000 kB\nMemAvailable: 400 kB\nOther: 5 kB\n"
        monkeypatch.setattr("builtins.open", mock.mock_open(read_data=content))
        total, avail = scanner._leer_meminfo()
        assert total == 1000 * 1024
        assert avail == 400 * 1024

    def test_statvfs_disk_total_cero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        s = mock.Mock()
        s.f_frsize = 4096
        s.f_blocks = 0
        s.f_bfree = 0
        monkeypatch.setattr(scanner.os, "statvfs", mock.Mock(return_value=s))
        assert scanner._leer_statvfs() == (0, 0, 0)

    def test_statvfs_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scanner.os, "statvfs", mock.Mock(side_effect=OSError("x")))
        assert scanner._leer_statvfs() == (0, 0, 0)

    def test_zombies_proc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_proc = mock.Mock()
        p1 = mock.Mock()
        p1.name = "123"
        p1.__truediv__ = mock.Mock(return_value=mock.Mock(read_text=mock.Mock(return_value="State:\tZ\n")))
        p2 = mock.Mock()
        p2.name = "notdigit"
        fake_proc.iterdir.return_value = [p1, p2]
        monkeypatch.setattr(Path, "iterdir", fake_proc.iterdir)
        assert scanner._contar_zombies_proc() == 1

    def test_zombies_proc_no_zombie(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_proc = mock.Mock()
        p1 = mock.Mock()
        p1.name = "123"
        p1.__truediv__ = mock.Mock(return_value=mock.Mock(read_text=mock.Mock(return_value="State:\tR\n")))
        fake_proc.iterdir.return_value = [p1]
        monkeypatch.setattr(Path, "iterdir", fake_proc.iterdir)
        assert scanner._contar_zombies_proc() == 0

    def test_zombies_proc_read_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_proc = mock.Mock()
        p1 = mock.Mock()
        p1.name = "123"
        p1.__truediv__ = mock.Mock(return_value=mock.Mock(read_text=mock.Mock(side_effect=OSError("x"))))
        fake_proc.iterdir.return_value = [p1]
        monkeypatch.setattr(Path, "iterdir", fake_proc.iterdir)
        with mock.patch.object(scanner.log, "debug"):
            assert scanner._contar_zombies_proc() == 0

    def test_zombies_proc_iter_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_proc = mock.Mock()
        fake_proc.iterdir.side_effect = OSError("x")
        monkeypatch.setattr(Path, "iterdir", fake_proc.iterdir)
        with mock.patch.object(scanner.log, "debug"):
            assert scanner._contar_zombies_proc() == 0


class TestHelpers:
    def test_pid_files_stale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        orphans: list[dict] = []
        stale = mock.Mock()
        stale.name = "x.pid"
        stale.read_text.return_value = "99999"
        fake_dir = mock.Mock()
        fake_dir.glob.return_value = [stale]
        proc = mock.Mock()
        proc.exists.return_value = False
        fake_path = mock.Mock(side_effect=lambda p: fake_dir if p == "/var/run" else proc)
        monkeypatch.setattr(scanner, "Path", fake_path)
        scanner._detectar_pid_files(orphans)
        assert len(orphans) == 1
        assert orphans[0]["tipo"] == "stale_pid"

    def test_pid_files_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        orphans: list[dict] = []
        bad = mock.Mock()
        bad.name = "bad.pid"
        bad.read_text.side_effect = ValueError("no int")
        fake_dir = mock.Mock()
        fake_dir.glob.return_value = [bad]
        fake_path = mock.Mock(side_effect=lambda p: fake_dir if p == "/var/run" else mock.Mock())
        monkeypatch.setattr(scanner, "Path", fake_path)
        with mock.patch.object(scanner.log, "debug"):
            scanner._detectar_pid_files(orphans)
        assert orphans == []

    def test_pid_files_glob_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_dir = mock.Mock()
        fake_dir.glob.side_effect = OSError("x")
        fake_path = mock.Mock(side_effect=lambda p: fake_dir)
        monkeypatch.setattr(scanner, "Path", fake_path)
        with mock.patch.object(scanner.log, "debug"):
            scanner._detectar_pid_files([])

    def test_hijos_huerfanos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        orphans: list[dict] = []
        fake_psutil = mock.Mock()
        orphan = {"pid": 111, "ppid": 999, "name": "weird"}
        normal = {"pid": 222, "ppid": 1, "name": "ok"}
        fake_psutil.process_iter.return_value = [mock.Mock(info=orphan), mock.Mock(info=normal)]
        import sys
        monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
        scanner._detectar_hijos_huerfanos(orphans)
        assert len(orphans) == 1
        assert orphans[0]["tipo"] == "hijo_huertano"

    def test_hijos_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        monkeypatch.delitem(sys.modules, "psutil", raising=False)
        fake = mock.Mock()
        fake.process_iter.side_effect = ImportError("no psutil")
        monkeypatch.setitem(sys.modules, "psutil", fake)
        scanner._detectar_hijos_huerfanos([])

    def test_docker_dangling(self, executor: FakeExecutor) -> None:
        executor.outputs["docker"] = "img1\nimg2\n"
        orphans: list[dict] = []
        scanner._detectar_docker_dangling(orphans, executor)
        assert orphans == [{"tipo": "docker_dangling", "cantidad": 2}]

    def test_docker_dangling_vacio(self, executor: FakeExecutor) -> None:
        executor.default = ""
        orphans: list[dict] = []
        scanner._detectar_docker_dangling(orphans, executor)
        assert orphans == []

    def test_docker_dangling_error(self, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("x"))
        scanner._detectar_docker_dangling([], executor)

    def test_systemd_failed_helper(self, executor: FakeExecutor) -> None:
        executor.default = "● x.service loaded failed failed\n"
        orphans: list[dict] = []
        scanner._detectar_systemd_failed(orphans, executor)
        assert orphans[0]["tipo"] == "systemd_failed"

    def test_systemd_failed_helper_error(self, executor: FakeExecutor) -> None:
        executor.run = mock.Mock(side_effect=RuntimeError("x"))
        scanner._detectar_systemd_failed([], executor)


class TestRecursosPsutil:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        fake_psutil = mock.Mock()
        fake_psutil.virtual_memory.return_value = mock.Mock(percent=10.0, total=1e9, available=9e8)
        fake_psutil.disk_usage.return_value = mock.Mock(percent=5.0, total=2e9, free=19e8)
        fake_psutil.getloadavg.return_value = (0.1, 0.1, 0.1)
        fake_psutil.cpu_count.return_value = 8
        fake_psutil.process_iter.return_value = []
        monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
        r = scanner._recursos_psutil()
        assert r is not None
        assert r["ram_pct"] == 10.0

    def test_excepcion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        fake_psutil = mock.Mock()
        fake_psutil.virtual_memory.side_effect = RuntimeError("x")
        monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
        with mock.patch.object(scanner.log, "warning"):
            assert scanner._recursos_psutil() is None

    def test_import_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        fake_psutil = mock.Mock()
        fake_psutil.virtual_memory.side_effect = ImportError("no")
        monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
        with mock.patch.object(scanner.log, "debug"):
            assert scanner._recursos_psutil() is None
