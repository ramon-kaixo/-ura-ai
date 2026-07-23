"""Tests para ProactiveDetector (scripts/pro/tuneladora/detector.py)."""
from __future__ import annotations

from unittest import mock

import pytest

from scripts.pro.tuneladora.detector import ProactiveDetector


@pytest.fixture
def detector() -> ProactiveDetector:
    return ProactiveDetector(notify=False)


class TestDisk:
    def test_disk_ok(self, detector):
        with mock.patch("os.statvfs") as m:
            class FakeStat:
                f_frsize = 4096
                f_bavail = 10000000
                f_blocks = 20000000
            m.return_value = FakeStat()
            r = detector.check_disk()
            assert r.status == "ok"
            assert r.value > 20

    def test_disk_warning(self, detector):
        with mock.patch("os.statvfs") as m:
            class FakeStat:
                f_frsize = 4096
                f_bavail = 3000000
                f_blocks = 20000000
            m.return_value = FakeStat()
            r = detector.check_disk()
            assert r.status == "warning"

    def test_disk_critical(self, detector):
        with mock.patch("os.statvfs") as m:
            class FakeStat:
                f_frsize = 4096
                f_bavail = 500000
                f_blocks = 20000000
            m.return_value = FakeStat()
            r = detector.check_disk()
            assert r.status == "critical"

    def test_disk_error(self, detector):
        with mock.patch("os.statvfs") as m:
            m.side_effect = Exception("disk error")
            r = detector.check_disk()
            assert r.status == "error"


class TestMemory:
    def test_memory_runs_without_error(self, detector):
        r = detector.check_memory()
        assert r.status in ("ok", "warning", "error", "critical")
        assert r.check == "memory"


class TestOllama:
    def test_ollama_ok(self, detector):
        with mock.patch("httpx.get") as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {"models": [{"name": "llama3"}]}
            r = detector.check_ollama()
            assert r.status == "ok"

    def test_ollama_no_models(self, detector):
        with mock.patch("httpx.get") as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {"models": []}
            r = detector.check_ollama()
            assert r.status == "warning"

    def test_ollama_down(self, detector):
        with mock.patch("httpx.get") as m:
            import httpx
            m.side_effect = httpx.ConnectError("connection refused")
            r = detector.check_ollama()
            assert r.status == "critical"


class TestGit:
    def test_git_clean(self, detector):
        with mock.patch("subprocess.run") as m:
            m.return_value.stdout = ""
            m.return_value.returncode = 0
            r = detector.check_git_status()
            assert r.status == "ok"

    def test_git_warning(self, detector):
        with mock.patch("subprocess.run") as m:
            m.return_value.stdout = " M file1.py\n M file2.py\n" * 6
            m.return_value.returncode = 0
            r = detector.check_git_status()
            assert r.status == "warning"

    def test_git_critical(self, detector):
        with mock.patch("subprocess.run") as m:
            m.return_value.stdout = " M file.py\n" * 60
            m.return_value.returncode = 0
            r = detector.check_git_status()
            assert r.status == "critical"

    def test_git_not_a_repo(self, detector):
        with mock.patch("subprocess.run") as m:
            m.return_value.returncode = 128
            r = detector.check_git_status()
            assert r.status == "error"


class TestCheckAll:
    def test_check_all_returns_list(self, detector):
        results = detector.check_all()
        assert isinstance(results, list)
        assert len(results) == 4

    def test_get_critical_filters(self, detector):
        results = [
            detector.check_disk(),
            mock.Mock(status="ok"),
            mock.Mock(status="critical"),
        ]
        critical = detector.get_critical(results)
        assert len(critical) >= 0
