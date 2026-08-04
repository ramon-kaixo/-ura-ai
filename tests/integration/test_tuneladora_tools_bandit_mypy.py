"""Tests para tools/bandit_tool.py y tools/mypy_tool.py."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts.pro.tuneladora.pipeline.tools.bandit_tool import BanditTool
from scripts.pro.tuneladora.pipeline.tools.base import Status
from scripts.pro.tuneladora.pipeline.tools.mypy_tool import MypyTool


class TestBanditTool:
    def test_is_available_ok(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
        )
        assert BanditTool(tmp_path).is_available() is True

    def test_is_available_fail(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=""),
        )
        assert BanditTool(tmp_path).is_available() is False

    def test_is_available_error(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("x")))
        assert BanditTool(tmp_path).is_available() is False

    def test_run_check_ok(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="No issues identified", stderr=""),
        )
        result = BanditTool(tmp_path).run_check(["a.py"])
        assert result.status == Status.OK
        assert result.seconds >= 0

    def test_run_check_fail_por_severidad(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(
                returncode=1,
                stdout="Severity: High\nSeverity: High\nSeverity: Medium\nSeverity: Low",
                stderr="",
            ),
        )
        result = BanditTool(tmp_path).run_check()
        assert result.status == Status.FAIL
        assert "2 high, 1 medium" in result.summary

    def test_run_check_sin_targets_usa_r(self, tmp_path: Path, monkeypatch) -> None:
        capturado: list = []

        def fake_run(cmd, **kwargs):
            capturado.append(cmd)
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)
        BanditTool(tmp_path).run_check()
        assert "-r" in capturado[0] and "." in capturado[0]

    def test_run_check_timeout(self, tmp_path: Path, monkeypatch) -> None:
        import subprocess

        monkeypatch.setattr(
            "subprocess.run",
            mock.Mock(side_effect=subprocess.TimeoutExpired(cmd="x", timeout=120)),
        )
        result = BanditTool(tmp_path).run_check()
        assert result.status == Status.FAIL
        assert "Timeout" in result.summary

    def test_run_check_error(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("x")))
        result = BanditTool(tmp_path).run_check()
        assert result.status == Status.FAIL

    def test_run_fix_delega(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        )
        result = BanditTool(tmp_path).run_fix(["a.py"])
        assert result.status == Status.OK

    def test_severity(self, tmp_path: Path) -> None:
        assert BanditTool(tmp_path).severity() == "required"


class TestMypyTool:
    def test_is_available_ok(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
        )
        assert MypyTool(tmp_path).is_available() is True

    def test_is_available_fail(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=""),
        )
        assert MypyTool(tmp_path).is_available() is False

    def test_run_check_ok(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="Success: no issues", stderr=""),
        )
        result = MypyTool(tmp_path).run_check(["a.py"])
        assert result.status == Status.OK

    def test_run_check_fail(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=1, stdout="error: found issues", stderr=""),
        )
        result = MypyTool(tmp_path).run_check(["a.py"])
        assert result.status == Status.WARN

    def test_run_check_timeout(self, tmp_path: Path, monkeypatch) -> None:
        import subprocess

        monkeypatch.setattr(
            "subprocess.run",
            mock.Mock(side_effect=subprocess.TimeoutExpired(cmd="x", timeout=120)),
        )
        result = MypyTool(tmp_path).run_check()
        assert result.status == Status.WARN
        assert "Timeout" in result.summary

    def test_run_check_error(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("x")))
        result = MypyTool(tmp_path).run_check()
        assert result.status == Status.WARN

    def test_run_fix(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        )
        result = MypyTool(tmp_path).run_fix()
        assert result.status == Status.OK

    def test_severity(self, tmp_path: Path) -> None:
        assert MypyTool(tmp_path).severity() == "optional"
