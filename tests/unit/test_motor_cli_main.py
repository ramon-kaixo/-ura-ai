"""Tests para motor/cli/main.py — dispatch de comandos CLI."""

import logging
from unittest import mock
from unittest.mock import call

import pytest

from motor.cli import main


@pytest.fixture(autouse=True)
def _patched_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aisla todos los comandos para no ejecutar lógica real."""
    mock_commands = {name: mock.Mock() for name in main.COMMANDS}
    mock_ura = {name: mock.Mock() for name in main.URA_COMMANDS}
    monkeypatch.setattr(main, "COMMANDS", mock_commands)
    monkeypatch.setattr(main, "URA_COMMANDS", mock_ura)


def test_setup_logging_default(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = mock.Mock()
    with mock.patch("motor.cli.main.logging.StreamHandler", return_value=handler), \
            mock.patch("motor.cli.main.logging.Formatter"), \
            mock.patch("motor.cli.main.logging.getLogger") as get_logger:
        main._setup_logging("info")
        root = get_logger.return_value
        root.addHandler.assert_called_once_with(handler)
        assert call(logging.INFO) in root.setLevel.call_args_list


def test_setup_logging_invalido(monkeypatch: pytest.MonkeyPatch) -> None:
    with mock.patch("motor.cli.main.logging.StreamHandler", return_value=mock.Mock()), \
            mock.patch("motor.cli.main.logging.Formatter"), \
            mock.patch("motor.cli.main.logging.getLogger") as get_logger:
        main._setup_logging("NOEXISTE")
        assert call(logging.INFO) in get_logger.return_value.setLevel.call_args_list


def test_main_command_ura_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada comando URA con raw args y sys.exit."""
    fake_cfg = mock.Mock()
    fake_cfg.log_level = "INFO"
    with mock.patch("motor.cli.main.UraConfig.load", return_value=fake_cfg), \
            mock.patch("motor.cli.main.sys.exit") as sys_exit:
        for name in (
            "finalize", "test", "snapshot", "maintenance", "clean", "rotate",
            "health", "alerts", "logs", "snc", "heartbeat", "doctor",
            "metrics", "dashboard", "index", "ask", "memory",
        ):
            with mock.patch("motor.cli.main.sys.argv", ["ura", name, "-m", "x"]):
                main.main()
            main.URA_COMMANDS[name].assert_called_once()
            sys_exit.assert_called()
            sys_exit.reset_mock()


def test_main_command_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada comando normal (sin sys.exit)."""
    fake_cfg = mock.Mock()
    fake_cfg.log_level = "INFO"
    with mock.patch("motor.cli.main.UraConfig.load", return_value=fake_cfg), \
            mock.patch("motor.cli.main.sys.exit") as sys_exit:
        for name in (
            "pipeline", "scan", "diagnose", "calibrate", "status", "cross",
            "trend", "graph", "perf", "summarise", "history", "check",
            "verify", "detect", "learn", "alerta", "health-check",
            "qdrant-backup", "notify", "bench",
        ):
            with mock.patch("motor.cli.main.sys.argv", ["ura", name]):
                main.main()
            main.COMMANDS[name].assert_called_once()
            sys_exit.assert_not_called()
            sys_exit.reset_mock()


def test_main_sin_comando(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin comando → SystemExit (argparse required)."""
    with mock.patch("motor.cli.main.sys.argv", ["ura"]):
        with pytest.raises(SystemExit):
            main.main()


def test_main_flag_config(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cfg = mock.Mock()
    fake_cfg.log_level = "INFO"
    fake_cls = mock.Mock(return_value=fake_cfg)
    fake_cls.load.return_value = fake_cfg
    with mock.patch("motor.cli.main.UraConfig", fake_cls), \
            mock.patch("motor.cli.main.sys.argv", ["ura", "--config", "/tmp/c.json", "status"]):
        main.main()
    fake_cls.load.assert_called_once_with("/tmp/c.json")
    assert fake_cfg.log_level == "INFO"


def test_main_command_log_level_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cfg = mock.Mock()
    fake_cfg.log_level = "INFO"
    fake_cls = mock.Mock(return_value=fake_cfg)
    fake_cls.load.return_value = fake_cfg
    with mock.patch("motor.cli.main.UraConfig", fake_cls), \
            mock.patch("motor.cli.main.sys.argv", ["ura", "--log-level", "DEBUG", "pipeline"]):
        main.main()
    assert fake_cfg.log_level == "DEBUG"
