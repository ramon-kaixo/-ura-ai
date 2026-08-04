"""Tests para scripts/pro/tuneladora/scheduler_daemon.py y install_service.py."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import threading
from unittest import mock

import pytest

import scripts.pro.tuneladora.install_service as isvc
import scripts.pro.tuneladora.scheduler_daemon as daemon


class TestInstallService:
    def test_no_root(self, monkeypatch) -> None:
        monkeypatch.setattr("os.geteuid", lambda: 1000)
        result = isvc.install_service()
        assert result["ok"] is False
        assert "sudo" in result["error"]

    def test_archivo_no_existe(self, monkeypatch) -> None:
        monkeypatch.setattr("os.geteuid", lambda: 0)

        class FakeNoExist(Path):
            def exists(self) -> bool:
                return False

        monkeypatch.setattr(isvc, "Path", FakeNoExist)
        result = isvc.install_service()
        assert result["ok"] is False
        assert "no encontrado" in result["error"]

    def test_permiso_denegado(self, monkeypatch) -> None:
        monkeypatch.setattr("os.geteuid", lambda: 0)
        monkeypatch.setattr(isvc.shutil, "copy2", mock.Mock(side_effect=PermissionError("nope")))
        result = isvc.install_service()
        assert result["ok"] is False
        assert result["copy"] == "denied (need sudo)"

    def test_instalacion_ok(self, monkeypatch) -> None:
        monkeypatch.setattr("os.geteuid", lambda: 0)
        monkeypatch.setattr(isvc.shutil, "copy2", mock.Mock())

        def fake_run(cmd, **kwargs):
            if "status" in cmd:
                return mock.Mock(returncode=0, stdout="active (running)", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(isvc.subprocess, "run", fake_run)
        result = isvc.install_service()
        assert result["ok"] is True
        assert result["copy"] == "ok"
        assert result["start"] == "ok"
        assert result["status"] == "active"

    def test_fallo_en_start(self, monkeypatch) -> None:
        monkeypatch.setattr("os.geteuid", lambda: 0)
        monkeypatch.setattr(isvc.shutil, "copy2", mock.Mock())

        def fake_run(cmd, **kwargs):
            if "status" in cmd:
                return mock.Mock(returncode=0, stdout="inactive", stderr="")
            if "start" in cmd:
                return mock.Mock(returncode=1, stdout="", stderr="unit not found")
            return mock.Mock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(isvc.subprocess, "run", fake_run)
        result = isvc.install_service()
        assert result["ok"] is False
        assert "unit not found" in result["start"]


class TestSchedulerDaemon:
    def test_shutdown(self) -> None:
        daemon.scheduler = mock.Mock()
        with mock.patch.object(daemon.sys, "exit") as m_exit:
            daemon._shutdown(15, None)
        daemon.scheduler.stop.assert_called_once()
        m_exit.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_main_arranca_y_detiene(self, monkeypatch) -> None:
        scheduler = mock.Mock()
        scheduler.pipeline_count = 3
        monkeypatch.setattr(daemon, "TuneladoraScheduler", mock.Mock(return_value=scheduler))
        monkeypatch.setattr(daemon, "signal", mock.Mock())
        monkeypatch.setattr(daemon, "DashboardPlugin", mock.Mock())
        thread = mock.Mock()
        monkeypatch.setattr(daemon.threading, "Thread", mock.Mock(return_value=thread))
        monkeypatch.setattr(daemon, "_shutdown", mock.Mock())
        fake_asyncio = mock.Mock()
        fake_asyncio.CancelledError = asyncio.CancelledError
        fake_asyncio.sleep = mock.AsyncMock(side_effect=asyncio.CancelledError)
        monkeypatch.setattr(daemon, "asyncio", fake_asyncio)

        await daemon.main()
        scheduler.start.assert_called_once()
        assert scheduler.add_pipeline.call_count == 3
        thread.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_falla_no_crashea(self, monkeypatch) -> None:
        scheduler = mock.Mock()
        monkeypatch.setattr(daemon, "TuneladoraScheduler", mock.Mock(return_value=scheduler))
        monkeypatch.setattr(daemon, "signal", mock.Mock())
        monkeypatch.setattr(daemon, "DashboardPlugin", mock.Mock(side_effect=RuntimeError("port busy")))
        monkeypatch.setattr(daemon, "_shutdown", mock.Mock())
        fake_asyncio = mock.Mock()
        fake_asyncio.CancelledError = asyncio.CancelledError
        fake_asyncio.sleep = mock.AsyncMock(side_effect=asyncio.CancelledError)
        monkeypatch.setattr(daemon, "asyncio", fake_asyncio)

        await daemon.main()  # no debe lanzar
