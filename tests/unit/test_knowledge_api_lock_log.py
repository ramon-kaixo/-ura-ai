"""Tests para knowledge/engine/ — cli/api, logging_config y lock."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from knowledge.engine.lock import LockAcquisitionError, compile_lock


class TestCmdApi:
    def test_con_auth(self, monkeypatch) -> None:
        from knowledge.engine.cli.api import cmd_api

        uvicorn_run = mock.Mock()
        monkeypatch.setattr("uvicorn.run", uvicorn_run)
        monkeypatch.setattr("knowledge.engine.cli.api.get_secret", mock.Mock(return_value=""))
        monkeypatch.setattr("knowledge.engine.cli.api.sys.stdout", mock.Mock())
        monkeypatch.delenv("URA_API_KEY", raising=False)
        args = mock.Mock()
        args.port = 4097
        args.host = "127.0.0.1"
        args.auth = "mi-clave"
        assert cmd_api(args) == 0
        uvicorn_run.assert_called_once()
        assert "URA_API_KEY" in __import__("os").environ
        assert uvicorn_run.call_args.args[0] == "knowledge.engine.api:app"

    def test_auth_desde_env(self, monkeypatch) -> None:
        from knowledge.engine.cli.api import cmd_api

        uvicorn_run = mock.Mock()
        monkeypatch.setattr("uvicorn.run", uvicorn_run)
        monkeypatch.setattr("knowledge.engine.cli.api.get_secret", mock.Mock(return_value="env-key"))
        monkeypatch.setattr("knowledge.engine.cli.api.sys.stdout", mock.Mock())
        monkeypatch.delenv("URA_API_KEY", raising=False)
        args = mock.Mock()
        args.port = 4097
        args.host = "127.0.0.1"
        args.auth = None
        cmd_api(args)
        assert __import__("os").environ["URA_API_KEY"] == "env-key"

    def test_sin_auth_localhost(self, monkeypatch) -> None:
        from knowledge.engine.cli.api import cmd_api

        uvicorn_run = mock.Mock()
        monkeypatch.setattr("uvicorn.run", uvicorn_run)
        monkeypatch.setattr("knowledge.engine.cli.api.get_secret", mock.Mock(return_value=""))
        monkeypatch.setattr("knowledge.engine.cli.api.sys.stdout", mock.Mock())
        monkeypatch.delenv("URA_API_KEY", raising=False)
        args = mock.Mock()
        args.port = 4097
        args.host = "127.0.0.1"
        args.auth = None
        cmd_api(args)  # no debe lanzar


class TestLoggingConfig:
    def test_deprecation_warning(self) -> None:
        from knowledge.engine.logging_config import setup_logging

        with pytest.warns(DeprecationWarning, match="deprecated"):
            setup_logging()

    def test_setup_json(self, monkeypatch) -> None:
        from knowledge.engine.logging_config import setup_logging

        monkeypatch.setenv("URA_STRUCTURED_LOGS", "true")
        setup_mock = mock.Mock()
        monkeypatch.setattr("knowledge.engine.logging_config._setup_logging", setup_mock)
        with pytest.warns(DeprecationWarning):
            setup_logging()
        setup_mock.assert_called_once_with(level="INFO", json_output=True)

    def test_exports(self) -> None:
        from knowledge.engine.logging_config import set_correlation_id, setup_logging

        assert callable(setup_logging)
        assert callable(set_correlation_id)


class TestCompileLock:
    def test_adquiere_y_libera(self, tmp_path) -> None:
        lock_file = tmp_path / "compile.lock"
        with compile_lock(lock_file):
            assert lock_file.exists()
        # liberado: se puede re-adquirir
        with compile_lock(lock_file):
            pass

    def test_conflicto(self, tmp_path) -> None:
        lock_file = tmp_path / "compile.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        import os as _os

        fd = _os.open(str(lock_file), _os.O_CREAT | _os.O_RDWR, 0o644)
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with pytest.raises(LockAcquisitionError, match="Compile ya en ejecución"):
                with compile_lock(lock_file):
                    pass
        finally:
            _os.close(fd)

    def test_crea_dir(self, tmp_path) -> None:
        lock_file = tmp_path / "sub" / "compile.lock"
        with compile_lock(lock_file):
            assert lock_file.exists()
