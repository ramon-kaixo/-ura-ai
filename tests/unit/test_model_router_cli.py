"""Tests para core/model_router/cli.py."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

import core.model_router.cli as cli


class TestVerificarPoliticas:
    def test_elimina_bypass_y_exit_sin_token(self, monkeypatch, tmp_path) -> None:
        bypass = tmp_path / "bypass_config.json"
        bypass.write_text("{}")
        monkeypatch.setattr(cli, "BYPASS_FILE", bypass)
        monkeypatch.setattr("motor.core.secrets.get_secret", mock.Mock(return_value=None))
        monkeypatch.setattr(cli.sys, "exit", mock.Mock(side_effect=SystemExit(78)))
        with pytest.raises(SystemExit) as e:
            cli.verificar_politicas_seguridad_preflight()
        assert e.value.code == 78
        assert not bypass.exists()
        assert cli.os.environ.get("URA_AUTH_ENABLED") == "true"

    def test_con_token_no_exit(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(cli, "BYPASS_FILE", tmp_path / "nope.json")
        monkeypatch.setattr("motor.core.secrets.get_secret", mock.Mock(return_value="tok"))
        monkeypatch.setattr(cli.sys, "exit", mock.Mock(side_effect=SystemExit(99)))
        cli.verificar_politicas_seguridad_preflight()  # no debe hacer exit


class TestMain:
    def test_test_flag(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["cli.py", "--test", "analizar algo"])
        monkeypatch.setattr(cli, "setup_logging", mock.Mock())
        seleccionar = mock.Mock()
        monkeypatch.setattr("core.model_router.model_selection.seleccionar_modelo", seleccionar)
        cli.main()
        seleccionar.assert_called_once()

    def test_models_flag(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["cli.py", "--models"])
        monkeypatch.setattr(cli, "setup_logging", mock.Mock())
        monkeypatch.setattr("core.model_router.model_selection.obtener_modelos_disponibles", mock.Mock(return_value=[]))
        cli.main()  # no debe lanzar

    def test_sin_flags_llama_preflight(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["cli.py"])
        monkeypatch.setattr(cli, "setup_logging", mock.Mock())
        preflight = mock.Mock()
        monkeypatch.setattr(cli, "verificar_politicas_seguridad_preflight", preflight)
        monkeypatch.setattr("core.model_router.router.get_ollama_url", mock.Mock(return_value="http://x"))
        monkeypatch.setattr("core.model_router.router.ROUTER_PORT", 9999)
        log = mock.Mock()
        monkeypatch.setattr(cli, "log", log)
        monkeypatch.setattr("core.model_router.model_selection.obtener_modelos_disponibles", mock.Mock(return_value=[]))
        cli.main()
        preflight.assert_called_once()
        log.info.assert_called()
