"""Tests para core/sandbox.py — Sandbox, safe_import, backup/rollback.

Nota: core/sandbox/ es un paquete (docker_orchestrator), por lo que
'import core.sandbox' resuelve al paquete, no al modulo raiz core/sandbox.py.
El modulo raiz es un muerto no importado por nadie — se carga via importlib
con ruta directa al archivo.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

_SANDBOX_FILE = Path(__file__).resolve().parent.parent.parent / "core" / "sandbox.py"
_spec = importlib.util.spec_from_file_location("_core_sandbox_mod", _SANDBOX_FILE)
assert _spec and _spec.loader
_sandbox_mod = importlib.util.module_from_spec(_spec)
sys.modules["_core_sandbox_mod"] = _sandbox_mod
_spec.loader.exec_module(_sandbox_mod)

Sandbox = _sandbox_mod.Sandbox
get_sandbox = _sandbox_mod.get_sandbox


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch):
    import _core_sandbox_mod as mod

    monkeypatch.setattr(mod, "_sandbox_instance", None)
    yield


@pytest.fixture
def sandbox(monkeypatch, tmp_path) -> Sandbox:
    import _core_sandbox_mod as mod

    monkeypatch.setattr(mod.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(mod, "SANDBOX_LOG", tmp_path / "sandbox.log")
    return Sandbox()


class TestLog:
    def test_log_escribe(self, sandbox: Sandbox, tmp_path) -> None:
        sandbox._log("TEST", "detalle")
        content = (tmp_path / "sandbox.log").read_text()
        assert "[TEST]" in content
        assert "detalle" in content

    def test_log_error_no_lanza(self, sandbox: Sandbox) -> None:
        with mock.patch("builtins.open", side_effect=OSError("ro")):
            sandbox._log("TEST", "x")  # no debe lanzar


class TestTestImprovement:
    @pytest.mark.asyncio
    async def test_exito(self, sandbox: Sandbox, monkeypatch) -> None:
        proc = mock.Mock()
        proc.returncode = 0
        proc.communicate = mock.AsyncMock(return_value=(b"salida", b""))
        import asyncio as _asyncio
        monkeypatch.setattr(_asyncio, "create_subprocess_exec", mock.AsyncMock(return_value=proc))
        r = await sandbox.test_improvement("mod", "print('hola')")
        assert r == {"success": True, "output": "salida", "error": ""}

    @pytest.mark.asyncio
    async def test_error_stderr(self, sandbox: Sandbox, monkeypatch) -> None:
        proc = mock.Mock()
        proc.returncode = 1
        proc.communicate = mock.AsyncMock(return_value=(b"", b"error de test"))
        import asyncio as _asyncio
        monkeypatch.setattr(_asyncio, "create_subprocess_exec", mock.AsyncMock(return_value=proc))
        r = await sandbox.test_improvement("mod", "x")
        assert r["success"] is False
        assert r["error"] == "error de test"

    @pytest.mark.asyncio
    async def test_timeout(self, sandbox: Sandbox, monkeypatch) -> None:
        proc = mock.Mock()
        proc.kill = mock.Mock()
        proc.wait = mock.AsyncMock()
        proc.communicate = mock.AsyncMock(side_effect=TimeoutError())
        import asyncio as _asyncio
        monkeypatch.setattr(_asyncio, "create_subprocess_exec", mock.AsyncMock(return_value=proc))
        r = await sandbox.test_improvement("mod", "x")
        assert r["success"] is False
        assert "Timeout" in r["error"]
        proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_excepcion_general(self, sandbox: Sandbox, monkeypatch) -> None:
        import asyncio as _asyncio
        monkeypatch.setattr(_asyncio, "create_subprocess_exec", mock.AsyncMock(side_effect=OSError("no python")))
        r = await sandbox.test_improvement("mod", "x")
        assert r["success"] is False
        assert "no python" in r["error"]

    @pytest.mark.asyncio
    async def test_archivo_temporal_limpiado(self, sandbox: Sandbox, monkeypatch, tmp_path) -> None:
        proc = mock.Mock()
        proc.returncode = 0
        proc.communicate = mock.AsyncMock(return_value=(b"", b""))
        import asyncio as _asyncio
        monkeypatch.setattr(_asyncio, "create_subprocess_exec", mock.AsyncMock(return_value=proc))
        ruta_creada = []

        real_named = __import__("tempfile").NamedTemporaryFile

        def fake_named(**kw):
            f = real_named(**kw)
            ruta_creada.append(f.name)
            return f

        monkeypatch.setattr("tempfile.NamedTemporaryFile", fake_named)
        await sandbox.test_improvement("mod", "print(1)")
        assert ruta_creada
        assert not Path(ruta_creada[0]).exists()


class TestSafeImport:
    def test_modulo_ok(self, sandbox: Sandbox) -> None:
        assert sandbox.safe_import("json") is True

    def test_modulo_no_encontrado(self, sandbox: Sandbox) -> None:
        assert sandbox.safe_import("modulo_inexistente_xyz") is False

    def test_error_carga(self, sandbox: Sandbox, monkeypatch) -> None:
        spec = SimpleNamespace(loader=None)
        monkeypatch.setattr("importlib.util.find_spec", mock.Mock(return_value=spec))
        assert sandbox.safe_import("algo") is False

    def test_excepcion_import(self, sandbox: Sandbox, monkeypatch) -> None:
        monkeypatch.setattr("importlib.util.find_spec", mock.Mock(side_effect=ImportError("boom")))
        assert sandbox.safe_import("algo") is False


class TestBackupRollback:
    def test_create_backup_ok(self, sandbox: Sandbox, tmp_path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("codigo")
        backup = sandbox.create_backup(str(src))
        assert backup is not None
        assert Path(backup).read_text() == "codigo"

    def test_create_backup_no_existe(self, sandbox: Sandbox) -> None:
        assert sandbox.create_backup("/tmp/no_existe_xyz.py") is None

    def test_create_backup_error(self, sandbox: Sandbox, monkeypatch) -> None:
        monkeypatch.setattr(_sandbox_mod.shutil, "copy2", mock.Mock(side_effect=OSError("ro")))
        src = Path("/tmp/existe_para_backup.py")
        src.write_text("x")
        try:
            assert sandbox.create_backup(str(src)) is None
        finally:
            src.unlink()

    def test_rollback_ok(self, sandbox: Sandbox, tmp_path) -> None:
        dest = tmp_path / "mod.py"
        dest.write_text("modificado")
        backup = tmp_path / "backup.py"
        backup.write_text("original")
        assert sandbox.rollback(str(dest), str(backup)) is True
        assert dest.read_text() == "original"

    def test_rollback_backup_no_existe(self, sandbox: Sandbox) -> None:
        assert sandbox.rollback("/tmp/d.py", "/tmp/no_backup.py") is False

    def test_rollback_error(self, sandbox: Sandbox, monkeypatch, tmp_path) -> None:
        backup = tmp_path / "b.py"
        backup.write_text("x")
        monkeypatch.setattr(_sandbox_mod.shutil, "copy2", mock.Mock(side_effect=OSError("ro")))
        assert sandbox.rollback(str(tmp_path / "d.py"), str(backup)) is False


class TestCleanup:
    def test_elimina_antiguos(self, sandbox: Sandbox, tmp_path) -> None:
        bdir = tmp_path / ".ura" / "sandbox_backups"
        bdir.mkdir(parents=True, exist_ok=True)
        viejo = bdir / "viejo.py"
        nuevo = bdir / "nuevo.py"
        viejo.write_text("x")
        nuevo.write_text("x")
        import os
        import time

        antiguo_ts = time.time() - 10 * 86400
        os.utime(viejo, (antiguo_ts, antiguo_ts))
        sandbox.cleanup_old_backups(days=7)
        assert not viejo.exists()
        assert nuevo.exists()

    def test_cleanup_error(self, sandbox: Sandbox, monkeypatch, tmp_path) -> None:
        (tmp_path / "backups").mkdir(parents=True)
        monkeypatch.setattr(_sandbox_mod, "shutil", mock.Mock())
        sandbox.cleanup_old_backups()  # no debe lanzar


class TestSingleton:
    def test_get_sandbox_singleton(self) -> None:
        a = get_sandbox()
        b = get_sandbox()
        assert a is b
