"""Tests para core/seguridad/rollback_manager.py y core/mochila/app.py."""
from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from core.mochila.app import create_app
from core.seguridad.rollback_manager import RollbackManager


class TestRollbackManager:
    def test_ejecutar_git_ok(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        res = mock.Mock()
        res.stdout = "salida\n"
        with mock.patch("core.seguridad.rollback_manager.subprocess.run", return_value=res) as run:
            ok, out = mgr._ejecutar_git(["status"])
        assert ok is True
        assert out == "salida"
        run.assert_called_once()

    def test_ejecutar_git_error(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        err = mock.Mock()
        err.stderr = "fallo\n"
        with mock.patch("core.seguridad.rollback_manager.subprocess.run", side_effect=OSError if False else __import__("subprocess").CalledProcessError(1, "git", stderr=err.stderr)):
            ok, out = mgr._ejecutar_git(["stash"])
        assert ok is False
        assert "fallo" in out

    def test_pre_write_archivo_no_existe(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        assert mgr.pre_write(str(tmp_path / "nuevo.py")) is True

    def test_pre_write_stash(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        archivo = tmp_path / "a.py"
        archivo.write_text("x")
        with mock.patch.object(mgr, "_ejecutar_git", return_value=(True, "ok")) as git:
            assert mgr.pre_write(str(archivo)) is True
        args = git.call_args.args[0]
        assert args[0] == "stash"
        assert args[1] == "push"

    def test_safe_write(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        target = str(tmp_path / "dest.py")
        tmp = mgr.safe_write(target, "contenido")
        assert tmp == target + ".ura_tmp"
        assert Path(tmp).read_text() == "contenido"
        assert not Path(target).exists()

    def test_rollback_sin_archivo(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        target = str(tmp_path / "a.py")
        with mock.patch.object(mgr, "_ejecutar_git") as git:
            mgr.rollback(target)
        git.assert_not_called()

    def test_rollback_elimina_temp_y_checkout(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        target = tmp_path / "a.py"
        target.write_text("v1")
        (tmp_path / "a.py.ura_tmp").write_text("v2")
        with mock.patch.object(mgr, "_ejecutar_git", return_value=(True, "")) as git:
            mgr.rollback(str(target))
        assert not (tmp_path / "a.py.ura_tmp").exists()
        git.assert_called_once_with(["checkout", "HEAD", "--", "a.py"])

    def test_commit_if_valid_sin_temp(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        assert mgr.commit_if_valid(str(tmp_path / "a.py"), "task1") is False

    def test_commit_if_valid_ok(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        target = tmp_path / "a.py"
        target.write_text("v1")
        tmp = tmp_path / "a.py.ura_tmp"
        tmp.write_text("v2")
        with mock.patch.object(mgr, "_ejecutar_git", side_effect=[(True, ""), (True, "")]) as git:
            ok = mgr.commit_if_valid(str(target), "task1")
        assert ok is True
        assert target.read_text() == "v2"
        assert not tmp.exists()
        assert git.call_count == 2
        assert git.call_args_list[1].args[0][0] == "commit"

    def test_commit_if_valid_add_falla(self, tmp_path) -> None:
        mgr = RollbackManager(repo_path=str(tmp_path))
        target = tmp_path / "a.py"
        target.write_text("v1")
        (tmp_path / "a.py.ura_tmp").write_text("v2")
        with mock.patch.object(mgr, "_ejecutar_git", return_value=(False, "err")):
            assert mgr.commit_if_valid(str(target), "task1") is False


class TestCreateApp:
    def test_create_app_estructura(self) -> None:
        from fastapi import APIRouter
        with mock.patch("core.mochila.app.build_state"):
            with mock.patch("core.mochila.app.create_api_router", side_effect=lambda state: APIRouter()) as router:
                with mock.patch("core.mochila.app.load_dotenv"):
                    app = create_app()
        assert app.title == "Mochila Middleware"
        router.assert_called_once()

    def test_create_app_lifespan(self) -> None:
        import asyncio

        from fastapi import APIRouter

        from core.mochila.app import create_app

        state = mock.Mock()
        state.scheduler = mock.Mock()
        state.scheduler.start_loop = mock.AsyncMock()
        state.scheduler.stop_loop = mock.AsyncMock()
        state.providers = {}

        with mock.patch("core.mochila.app.build_state", return_value=state):
            with mock.patch("core.mochila.app.create_api_router", return_value=APIRouter()):
                with mock.patch("core.mochila.app.load_dotenv"):
                    with mock.patch("core.mochila.app.init_guardian"):
                        app2 = create_app()
        asyncio.run(app2.router.lifespan_context(app2).__aenter__())
        state.scheduler.start_loop.assert_awaited_once()

    def test_create_app_lifespan_exit_cierra_providers(self) -> None:
        from fastapi import APIRouter
        from fastapi.testclient import TestClient

        from core.mochila.app import create_app

        provider = mock.Mock()
        provider.__aenter__ = mock.AsyncMock(return_value=provider)
        provider.__aexit__ = mock.AsyncMock(return_value=False)
        state = mock.Mock()
        state.scheduler = mock.Mock()
        state.scheduler.start_loop = mock.AsyncMock()
        state.scheduler.stop_loop = mock.AsyncMock()
        state.providers = {"ollama": provider}

        with mock.patch("core.mochila.app.build_state", return_value=state):
            with mock.patch("core.mochila.app.create_api_router", return_value=APIRouter()):
                with mock.patch("core.mochila.app.load_dotenv"):
                    with mock.patch("core.mochila.app.init_guardian"):
                        app2 = create_app()
        with TestClient(app2) as client:
            assert client.get("/").status_code in (200, 404)
        provider.__aexit__.assert_awaited_once_with(None, None, None)
        state.scheduler.stop_loop.assert_awaited_once()
