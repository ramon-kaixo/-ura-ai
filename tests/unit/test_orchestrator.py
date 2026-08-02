"""Tests for scripts/pro/orchestrator.py."""
import subprocess

from scripts.pro.orchestrator import main


class TestOrchestrator:
    def test_main_suite_passes(self, monkeypatch):
        def fake_run(*a, **k):
            class R:
                returncode = 0
                stdout = "5 passed\n"
                stderr = ""

            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert main() == 0

    def test_main_suite_fails(self, monkeypatch):
        def fake_run(*a, **k):
            class R:
                returncode = 1
                stdout = "1 failed\n"
                stderr = "error de make"

            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert main() == 1
