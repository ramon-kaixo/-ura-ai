"""Tests para scripts/pro/tuneladora/detector.py (ProactiveDetector)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts.pro.tuneladora.detector import DetectionResult, ProactiveDetector


@pytest.fixture
def detector() -> ProactiveDetector:
    return ProactiveDetector(notify=False)


class _Stat:
    def __init__(self, frsize=4096, bavail=0, blocks=0):
        self.f_frsize = frsize
        self.f_bavail = bavail
        self.f_blocks = blocks


class TestCheckDisk:
    def test_ok(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("os.statvfs", lambda p: _Stat(bavail=5_000_000, blocks=10_000_000))
        r = detector.check_disk()
        assert r.status == "ok"
        assert r.value is not None

    def test_warning(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("os.statvfs", lambda p: _Stat(bavail=3_000_000, blocks=10_000_000))
        r = detector.check_disk()
        assert r.status == "warning"

    def test_critical(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("os.statvfs", lambda p: _Stat(bavail=1_000_000, blocks=10_000_000))
        r = detector.check_disk()
        assert r.status == "critical"

    def test_error(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("os.statvfs", mock.Mock(side_effect=OSError("x")))
        r = detector.check_disk()
        assert r.status == "error"

    def test_auto_cleanup_si_muy_critico(self, detector, monkeypatch) -> None:
        detector.engine = mock.Mock()
        calls = {"n": 0}

        def fake_statvfs(p):
            calls["n"] += 1
            if calls["n"] == 1:
                return _Stat(bavail=1_000_000, blocks=10_000_000)
            return _Stat(bavail=3_000_000, blocks=10_000_000)

        monkeypatch.setattr("os.statvfs", fake_statvfs)
        with mock.patch("scripts.pro.tuneladora.plugins.cleanup.CleanupPlugin") as m_cleanup:
            r = detector.check_disk()
        assert r.status == "warning"
        m_cleanup.return_value.cleanup_logs.assert_called_with(days=7)


class TestCheckMemory:
    def _meminfo(self, tmp_path: Path, total: int, avail: int) -> None:
        f = tmp_path / "meminfo"
        f.write_text(f"MemTotal: {total} kB\nMemAvailable: {avail} kB\n")
        monkeypatch_holder = {"p": f}

        import sys

        sys.modules["test_meminfo"] = sys.modules[__name__]
        return monkeypatch_holder

    def _patch_meminfo(self, monkeypatch, tmp_path: Path, total: int, avail: int) -> None:
        f = tmp_path / "meminfo"
        f.write_text(f"MemTotal: {total} kB\nMemAvailable: {avail} kB\n")
        from scripts.pro.tuneladora.detector import Path as _DetPath

        monkeypatch.setattr(_DetPath, "open", lambda self, *a, **k: open(f))

    def test_ok(self, detector, monkeypatch, tmp_path: Path) -> None:
        self._patch_meminfo(monkeypatch, tmp_path, 16_000_000, 8_000_000)
        r = detector.check_memory()
        assert r.status == "ok"
        assert r.value == 50.0

    def test_warning(self, detector, monkeypatch, tmp_path: Path) -> None:
        self._patch_meminfo(monkeypatch, tmp_path, 16_000_000, 2_000_000)
        r = detector.check_memory()
        assert r.status == "warning"

    def test_critical(self, detector, monkeypatch, tmp_path: Path) -> None:
        self._patch_meminfo(monkeypatch, tmp_path, 16_000_000, 500_000)
        r = detector.check_memory()
        assert r.status == "critical"

    def test_error(self, detector, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.Path.open",
            mock.Mock(side_effect=OSError("no meminfo")),
        )
        r = detector.check_memory()
        assert r.status == "error"


class TestCheckOllama:
    def test_ok_con_modelos(self, detector, monkeypatch) -> None:
        resp = SimpleNamespace(status_code=200, json=lambda: {"models": [1, 2, 3]})
        monkeypatch.setattr("httpx.get", lambda *a, **k: resp)
        r = detector.check_ollama()
        assert r.status == "ok"
        assert r.value == 3

    def test_cero_modelos_warning(self, detector, monkeypatch) -> None:
        resp = SimpleNamespace(status_code=200, json=lambda: {"models": []})
        monkeypatch.setattr("httpx.get", lambda *a, **k: resp)
        r = detector.check_ollama()
        assert r.status == "warning"

    def test_http_error_warning(self, detector, monkeypatch) -> None:
        resp = SimpleNamespace(status_code=500, json=lambda: {})
        monkeypatch.setattr("httpx.get", lambda *a, **k: resp)
        r = detector.check_ollama()
        assert r.status == "warning"

    def test_connect_error_critical_y_restart(self, detector, monkeypatch) -> None:
        import httpx

        monkeypatch.setattr("httpx.get", mock.Mock(side_effect=httpx.ConnectError("x")))
        with mock.patch.object(detector, "restart_ollama", return_value={"ok": True}) as m_restart:
            r = detector.check_ollama()
        assert r.status == "critical"
        m_restart.assert_called_once()

    def test_error_generico(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("httpx.get", mock.Mock(side_effect=RuntimeError("x")))
        r = detector.check_ollama()
        assert r.status == "error"


class TestCheckGit:
    def test_ok(self, detector, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout=""),
        )
        r = detector.check_git_status()
        assert r.status == "ok"

    def test_sucio_warning(self, detector, monkeypatch) -> None:
        out = "\n".join(f" M f{i}.py" for i in range(15))
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout=out),
        )
        r = detector.check_git_status()
        assert r.status == "warning"

    def test_muy_sucio_critical(self, detector, monkeypatch) -> None:
        out = "\n".join(f" M f{i}.py" for i in range(60))
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout=out),
        )
        r = detector.check_git_status()
        assert r.status == "critical"

    def test_no_repo(self, detector, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=128, stdout=""),
        )
        r = detector.check_git_status()
        assert r.status == "error"

    def test_error(self, detector, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            mock.Mock(side_effect=OSError("x")),
        )
        r = detector.check_git_status()
        assert r.status == "error"


class TestCheckAll:
    def test_ejecuta_todos(self, detector) -> None:
        with mock.patch.multiple(
            detector,
            check_disk=mock.DEFAULT,
            check_memory=mock.DEFAULT,
            check_ollama=mock.DEFAULT,
            check_git_status=mock.DEFAULT,
        ) as mocks:
            for m in mocks.values():
                m.return_value = DetectionResult("x", "ok", "msg")
            results = detector.check_all()
        assert len(results) == 4

    def test_get_critical(self) -> None:
        detector = ProactiveDetector(notify=False)
        results = [
            DetectionResult("a", "ok", "m"),
            DetectionResult("b", "critical", "m"),
            DetectionResult("c", "warning", "m"),
            DetectionResult("d", "critical", "m"),
        ]
        crit = detector.get_critical(results)
        assert len(crit) == 2
        assert all(r.status == "critical" for r in crit)


class TestAutoHealing:
    def test_restart_ollama_systemctl(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/systemctl")
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok"),
        )
        r = detector.restart_ollama()
        assert r["ok"] is True
        assert r["method"] == "systemctl"

    def test_restart_ollama_docker(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=1, stdout=""),
        )
        r = detector.restart_ollama()
        assert r["ok"] is False
        assert r["method"] == "docker"

    def test_restart_ollama_error(self, detector, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            mock.Mock(side_effect=OSError("x")),
        )
        r = detector.restart_ollama()
        assert r["ok"] is False

    def test_clear_zombies(self, detector, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.Path.iterdir",
            lambda self: iter([]),
        )
        r = detector.clear_zombies()
        assert r == {"ok": True, "killed": 0}

    def test_restart_service_ok(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/systemctl")
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout=""),
        )
        r = detector.restart_service("ura-tuneladora")
        assert r["ok"] is True
        assert r["service"] == "ura-tuneladora"

    def test_restart_service_sin_systemctl(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        r = detector.restart_service()
        assert r["ok"] is False

    def test_restart_service_error(self, detector, monkeypatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/systemctl")
        monkeypatch.setattr(
            "scripts.pro.tuneladora.detector.subprocess.run",
            mock.Mock(side_effect=OSError("x")),
        )
        r = detector.restart_service()
        assert r["ok"] is False


class TestAlert:
    def test_alerta_sin_alert_engine(self, detector) -> None:
        detector._alert_engine = None
        with mock.patch("scripts.pro.tuneladora.detector.log.warning") as m_warn:
            detector._alert("warning", "T", "D")
        m_warn.assert_called_once()

    def test_alerta_con_engine(self, detector) -> None:
        detector._notify = True
        detector._alert_engine = mock.Mock()
        detector._alert_engine._alert_history = []
        with mock.patch("scripts.pro.tuneladora.detector.Alert", return_value=mock.Mock()):
            detector._alert("critical", "T", "D")
        assert len(detector._alert_engine._alert_history) == 1

    def test_alerta_error_silencioso(self, detector) -> None:
        detector._alert_engine = mock.Mock()
        detector._alert_engine._alert_history = None
        with mock.patch(
            "scripts.pro.tuneladora.detector.Alert",
            mock.Mock(side_effect=TypeError("x")),
        ):
            detector._alert("warning", "T", "D")  # no debe lanzar
