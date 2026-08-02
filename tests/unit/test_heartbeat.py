"""Tests para core/infra/heartbeat.py."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

import core.infra.heartbeat as hb


class TestCheckHealth:
    def test_ok_con_token(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "get_secret", mock.Mock(return_value="tok"))
        resp = mock.Mock()
        resp.status = 200
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr(hb, "urlopen", mock.Mock(return_value=resp))
        assert hb.check_health() is True

    def test_ok_sin_token(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "get_secret", mock.Mock(return_value=""))
        resp = mock.Mock()
        resp.status = 200
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr(hb, "urlopen", mock.Mock(return_value=resp))
        assert hb.check_health() is True

    def test_status_no_200(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "get_secret", mock.Mock(return_value=""))
        resp = mock.Mock()
        resp.status = 503
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr(hb, "urlopen", mock.Mock(return_value=resp))
        assert hb.check_health() is False

    def test_error_red(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "get_secret", mock.Mock(return_value=""))
        monkeypatch.setattr(hb, "urlopen", mock.Mock(side_effect=OSError("net")))
        assert hb.check_health() is False


class TestDumpCheckpoint:
    def test_sin_checkpoint(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(hb, "STATE_FILE", str(tmp_path / "nope.json"))
        hb.dump_checkpoint()  # no debe lanzar

    def test_con_checkpoint(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "state.json"
        f.write_text(json.dumps({"task_id": "t1", "target_file": "f.py"}))
        monkeypatch.setattr(hb, "STATE_FILE", str(f))
        logger = mock.Mock()
        monkeypatch.setattr(hb, "logger", logger)
        hb.dump_checkpoint()
        logger.critical.assert_called_once()
        assert "t1" in logger.critical.call_args.args[1]

    def test_checkpoint_corrupto(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "state.json"
        f.write_text("no json")
        monkeypatch.setattr(hb, "STATE_FILE", str(f))
        logger = mock.Mock()
        monkeypatch.setattr(hb, "logger", logger)
        hb.dump_checkpoint()
        logger.warning.assert_called_once()


class TestSaveRestartQdrant:
    def test_error_instancia_inexistente(self, monkeypatch) -> None:
        """BUG REAL: 'from motor.core.qdrant_client import instancia' no existe
        (solo DegradedMode.instancia()). El ImportError es capturado y logueado —
        el incidente NUNCA se guarda. Test documenta el comportamiento actual."""
        logger = mock.Mock()
        monkeypatch.setattr(hb, "logger", logger)
        hb._save_restart_to_qdrant()  # no debe lanzar
        logger.exception.assert_called_once()


class TestRestartService:
    def test_ok(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "dump_checkpoint", mock.Mock())
        monkeypatch.setattr(hb, "_save_restart_to_qdrant", mock.Mock())
        res = SimpleNamespace(returncode=0, stderr="")
        monkeypatch.setattr(hb.subprocess, "run", mock.Mock(return_value=res))
        logger = mock.Mock()
        monkeypatch.setattr(hb, "logger", logger)
        hb.restart_service()
        logger.critical.assert_called_once()
        logger.info.assert_called_once()

    def test_fallo(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "dump_checkpoint", mock.Mock())
        monkeypatch.setattr(hb, "_save_restart_to_qdrant", mock.Mock())
        res = SimpleNamespace(returncode=1, stderr="error restart")
        monkeypatch.setattr(hb.subprocess, "run", mock.Mock(return_value=res))
        logger = mock.Mock()
        monkeypatch.setattr(hb, "logger", logger)
        hb.restart_service()
        logger.error.assert_called_once()

    def test_timeout(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "dump_checkpoint", mock.Mock())
        monkeypatch.setattr(hb, "_save_restart_to_qdrant", mock.Mock())
        monkeypatch.setattr(hb.subprocess, "run", mock.Mock(side_effect=__import__("subprocess").TimeoutExpired("c", 5)))
        hb.restart_service()  # no debe lanzar


class TestVramPressure:
    @pytest.fixture(autouse=True)
    def reset_cycles(self):
        hb.vram_critical_cycles = 0
        yield
        hb.vram_critical_cycles = 0

    def test_normal_reset(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="100\n200\n")
        monkeypatch.setattr(hb.subprocess, "run", mock.Mock(return_value=res))
        monkeypatch.setattr(hb, "log_event", mock.Mock())
        hb.check_vram_pressure()
        assert hb.vram_critical_cycles == 0

    def test_presion_acumula(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="25000\n")
        monkeypatch.setattr(hb.subprocess, "run", mock.Mock(return_value=res))
        monkeypatch.setattr(hb, "log_event", mock.Mock())
        hb.check_vram_pressure()
        assert hb.vram_critical_cycles == 1

    def test_panico_restart(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="25000\n")
        monkeypatch.setattr(hb.subprocess, "run", mock.Mock(return_value=res))
        monkeypatch.setattr(hb, "log_event", mock.Mock())
        restart = mock.Mock()
        monkeypatch.setattr(hb, "restart_service", restart)
        hb.vram_critical_cycles = 2
        hb.check_vram_pressure()
        restart.assert_called_once()
        assert hb.vram_critical_cycles == 0

    def test_error_monitor(self, monkeypatch) -> None:
        monkeypatch.setattr(hb.subprocess, "run", mock.Mock(side_effect=ValueError("bad")))
        monkeypatch.setattr(hb, "log_event", mock.Mock())
        hb.check_vram_pressure()  # no debe lanzar

    def test_salida_vacia(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0, stdout="")
        monkeypatch.setattr(hb.subprocess, "run", mock.Mock(return_value=res))
        hb.check_vram_pressure()
        assert hb.vram_critical_cycles == 0


class TestLoopLatency:
    def test_mide_latencia(self) -> None:
        lat = hb.check_loop_latency()
        assert lat >= 0.0


class TestMain:
    def test_una_ejecucion_ok(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "_shutdown_flag", False)
        monkeypatch.setattr("sys.argv", ["heartbeat.py"])
        monkeypatch.setattr(
            "argparse.ArgumentParser.parse_args",
            lambda self: SimpleNamespace(daemon=False),
        )
        monkeypatch.setattr(hb, "check_health", mock.Mock(return_value=True))
        monkeypatch.setattr(hb, "check_vram_pressure", mock.Mock())
        monkeypatch.setattr(hb, "check_loop_latency", mock.Mock(return_value=0.0))
        hb.main()  # no debe explotar ni iterar

    def test_tres_fallos_restart(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "_shutdown_flag", False)
        monkeypatch.setattr("sys.argv", ["heartbeat.py"])
        monkeypatch.setattr(
            "argparse.ArgumentParser.parse_args",
            lambda self: SimpleNamespace(daemon=False),
        )
        health = mock.Mock(side_effect=[False, False, False, True])
        monkeypatch.setattr(hb, "check_health", health)
        monkeypatch.setattr(hb, "check_vram_pressure", mock.Mock())
        monkeypatch.setattr(hb, "check_loop_latency", mock.Mock(return_value=0.0))
        restart = mock.Mock()

        def _fake_restart():
            restart()
            hb._shutdown_flag = True

        monkeypatch.setattr(hb, "restart_service", _fake_restart)
        monkeypatch.setattr(
            "argparse.ArgumentParser.parse_args",
            lambda self: SimpleNamespace(daemon=True),
        )
        monkeypatch.setattr(hb, "time", mock.Mock())
        hb.main()
        restart.assert_called_once()

    def test_latencia_alta_publica_alert(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "_shutdown_flag", False)
        monkeypatch.setattr("sys.argv", ["heartbeat.py"])
        monkeypatch.setattr(
            "argparse.ArgumentParser.parse_args",
            lambda self: SimpleNamespace(daemon=True),
        )
        monkeypatch.setattr(hb, "check_health", mock.Mock(return_value=True))
        monkeypatch.setattr(hb, "check_vram_pressure", mock.Mock())
        monkeypatch.setattr(hb, "check_loop_latency", mock.Mock(return_value=150.0))
        monkeypatch.setattr(hb.time, "sleep", mock.Mock(side_effect=SystemExit))
        monkeypatch.setattr(hb, "_shutdown_flag", False)
        publish = mock.Mock()
        monkeypatch.setattr("core.event_bus.publish", publish)
        monkeypatch.setattr(hb, "_shutdown_flag", False)
        hb.loop_latency_history.clear()
        with pytest.raises(SystemExit):
            hb.main()
        publish.assert_called_once()
        assert publish.call_args.args[0] == "alert"

    def test_latencia_baja_sin_alert(self, monkeypatch) -> None:
        monkeypatch.setattr(hb, "_shutdown_flag", False)
        monkeypatch.setattr("sys.argv", ["heartbeat.py"])
        monkeypatch.setattr(
            "argparse.ArgumentParser.parse_args",
            lambda self: SimpleNamespace(daemon=True),
        )
        monkeypatch.setattr(hb, "check_health", mock.Mock(return_value=True))
        monkeypatch.setattr(hb, "check_vram_pressure", mock.Mock())
        monkeypatch.setattr(hb, "check_loop_latency", mock.Mock(return_value=5.0))
        monkeypatch.setattr(hb.time, "sleep", mock.Mock(side_effect=SystemExit))
        publish = mock.Mock()
        monkeypatch.setattr("core.event_bus.publish", publish)
        monkeypatch.setattr(hb, "_shutdown_flag", False)
        hb.loop_latency_history.clear()
        with pytest.raises(SystemExit):
            hb.main()
        publish.assert_not_called()
