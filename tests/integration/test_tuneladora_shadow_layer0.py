"""Tests para scripts/pro/tuneladora/shadow/layer0_env.py."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts.pro.tuneladora.shadow.layer0_env import (
    EnvCheck,
    _disk_io_ok,
    _get_cpu_count,
    _get_ram_info,
    _git_available,
    _ollama_check,
    _session,
    run,
)


class TestSession:
    def test_crea_y_reusa(self) -> None:
        s1 = _session()
        s2 = _session()
        assert s1 is s2


class TestCpuCount:
    def test_normal(self, monkeypatch) -> None:
        monkeypatch.setattr("os.cpu_count", lambda: 8)
        assert _get_cpu_count() == 8

    def test_fallback(self, monkeypatch) -> None:
        monkeypatch.setattr("os.cpu_count", mock.Mock(side_effect=RuntimeError("x")))
        assert _get_cpu_count() == 1


class TestRamInfo:
    def test_con_psutil(self, monkeypatch) -> None:
        vm = SimpleNamespace(total=16 * 1024**3, available=8 * 1024**3, percent=50.0)
        monkeypatch.setitem(__import__("sys").modules, "psutil", SimpleNamespace(virtual_memory=lambda: vm))
        info = _get_ram_info()
        assert info["total_mb"] == 16384
        assert info["available_mb"] == 8192
        assert info["percent"] == 50.0

    def test_sin_psutil_con_proc(self, monkeypatch, tmp_path: Path) -> None:
        meminfo = tmp_path / "meminfo"
        meminfo.write_text("MemTotal:       16384000 kB\nMemAvailable:    8192000 kB\n")
        monkeypatch.setitem(__import__("sys").modules, "psutil", None)
        with mock.patch("pathlib.Path.open", return_value=meminfo.open()):
            info = _get_ram_info()
        assert info["total_mb"] == 16000
        assert info["available_mb"] == 8000

    def test_sin_psutil_fallback(self, monkeypatch) -> None:
        monkeypatch.setitem(__import__("sys").modules, "psutil", None)
        with mock.patch("pathlib.Path.open", side_effect=OSError("no proc")):
            info = _get_ram_info()
        assert info["available_mb"] == 2048


class TestOllamaCheck:
    def test_ok(self, monkeypatch) -> None:
        session = mock.Mock()
        session.get.return_value = SimpleNamespace(status_code=200, json=lambda: {"models": [1, 2, 3]})
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._session", lambda: session)
        ok, n = _ollama_check("http://x:11434")
        assert ok is True
        assert n == 3

    def test_no_200(self, monkeypatch) -> None:
        session = mock.Mock()
        session.get.return_value = SimpleNamespace(status_code=500, json=lambda: {})
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._session", lambda: session)
        assert _ollama_check("http://x") == (False, 0)

    def test_error(self, monkeypatch) -> None:
        session = mock.Mock()
        session.get.side_effect = RuntimeError("conn")
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._session", lambda: session)
        assert _ollama_check("http://x") == (False, 0)


class TestGitAvailable:
    def test_ok(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer0_env.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0),
        )
        assert _git_available(tmp_path) is True

    def test_fail(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer0_env.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=128),
        )
        assert _git_available(tmp_path) is False

    def test_error(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer0_env.subprocess.run",
            mock.Mock(side_effect=OSError("x")),
        )
        assert _git_available(tmp_path) is False


class TestDiskIo:
    def test_ok(self, tmp_path: Path) -> None:
        assert _disk_io_ok(tmp_path) is True

    def test_error(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer0_env.Path.write_text",
            mock.Mock(side_effect=OSError("ro")),
        )
        assert _disk_io_ok(tmp_path) is False


class TestRun:
    def test_todo_ok(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._free_disk_gb", lambda p: 50.0)
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer0_env._get_ram_info", lambda: {"percent": 50, "available_mb": 8000}
        )
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._ollama_check", lambda u: (True, 5))
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._get_cpu_count", lambda: 8)
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._git_available", lambda p: True)
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._disk_io_ok", lambda p: True)

        results = run(tmp_path)
        by_name = {r.name: r.status for r in results}
        assert by_name == {"disk": "OK", "ram": "OK", "ollama": "OK", "cpu": "OK", "git": "OK", "disk_io": "OK"}
        assert all(isinstance(r, EnvCheck) for r in results)

    def test_disk_fail_y_ram_warn(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._free_disk_gb", lambda p: 0.5)
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer0_env._get_ram_info", lambda: {"percent": 90, "available_mb": 100}
        )
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._ollama_check", lambda u: (False, 0))
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._get_cpu_count", lambda: 2)
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._git_available", lambda p: False)
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._disk_io_ok", lambda p: False)

        results = run(tmp_path)
        by_name = {r.name: r.status for r in results}
        assert by_name["disk"] == "FAIL"
        assert by_name["ram"] == "WARN"
        assert by_name["ollama"] == "WARN"
        assert by_name["git"] == "FAIL"
        assert by_name["disk_io"] == "WARN"

    def test_disk_indeterminado(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._free_disk_gb", lambda p: None)
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer0_env._get_ram_info", lambda: {"percent": 50, "available_mb": 8000}
        )
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._ollama_check", lambda u: (True, 1))
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._get_cpu_count", lambda: 4)
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._git_available", lambda p: True)
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.layer0_env._disk_io_ok", lambda p: True)

        results = run(tmp_path)
        assert results[0].status == "WARN"
