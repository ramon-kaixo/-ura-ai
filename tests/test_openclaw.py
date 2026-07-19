#!/usr/bin/env python3
"""Tests de integración — OpenClaw + SNC
Simula caídas de red y verifica que OpenClaw lee el estado EMERGENCY
y abre el emergency_runbook.json correctamente.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

# Setup path
ROOT = Path(__file__).parent.parent

from monitor.openclaw import (
    DEAD_MAN_TIMEOUT,
    execute_runbook_action,
    is_emergency,
    is_forbidden,
    load_runbook,
    load_state,
    process_emergency,
)


class TestOpenClawDeterminism(unittest.TestCase):
    """Tests de comportamiento determinista de OpenClaw."""

    def setUp(self) -> None:
        """Setup: crear state file temporal y runbook de prueba."""
        self.test_state = Path("/tmp/ura_snc_state_test.json")  # noqa: S108
        self.test_stats = Path("/tmp/ura_openclaw_stats_test.json")  # noqa: S108

        # Runbook de prueba
        self.test_runbook = {
            "version": "1.0",
            "commands": {
                "network": {
                    "description": "Red de prueba",
                    "check": "echo ok",
                    "repair": ["echo 'repairing network'"],
                    "timeout_after_repair": 5,
                },
                "ollama": {
                    "description": "Ollama de prueba",
                    "check": "echo ok",
                    "repair": ["echo 'restarting ollama'"],
                    "timeout_after_repair": 10,
                },
            },
            "forbidden_commands": ["rm -rf", "shutdown", "reboot", "halt"],
            "retry_policy": {"max_attempts": 3},
        }

    def tearDown(self) -> None:
        """Limpiar archivos temporales."""
        for f in [self.test_state, self.test_stats]:
            if f.exists():
                f.unlink()

    def test_runbook_loads_correctly(self) -> None:
        """Test: el runbook se carga correctamente y tiene version."""
        runbook = load_runbook()
        assert "version" in runbook
        assert "commands" in runbook
        assert "forbidden_commands" in runbook

    def test_state_file_reading(self) -> None:
        """Test: OpenClaw lee el state file escrito por SNC."""
        # Simular state file de emergencia
        emergency_state = {
            "timestamp": "2026-06-03T18:00:00",
            "status": "CRITICAL",
            "services": {
                "network": {"ok": False, "check": "ip link show enP7s7"},
                "ollama": {"ok": True, "check": "curl localhost:11434"},
            },
            "openclaw_active": True,
            "repair_attempts": {"network": 3},
        }
        self.test_state.write_text(json.dumps(emergency_state))

        with patch("monitor.openclaw.STATE_FILE", self.test_state):
            state = load_state()
            assert state["status"] == "CRITICAL"
            assert not state["services"]["network"]["ok"]
            assert state["services"]["ollama"]["ok"]

    def test_emergency_detection(self) -> None:
        """Test: OpenClaw detecta estado EMERGENCY."""
        critical = {"status": "CRITICAL"}
        emergency = {"status": "EMERGENCY"}
        ok = {"status": "OK"}
        unknown = {"status": "UNKNOWN"}

        assert is_emergency(critical)
        assert is_emergency(emergency)
        assert not is_emergency(ok)
        assert not is_emergency(unknown)

    def test_forbidden_commands_blocked(self) -> None:
        """Test: comandos prohibidos son bloqueados."""
        forbidden = ["rm -rf", "shutdown", "reboot", "halt"]

        assert is_forbidden("rm -rf /", forbidden)
        assert is_forbidden("shutdown -h now", forbidden)
        assert is_forbidden("reboot", forbidden)
        assert not is_forbidden("systemctl restart ollama", forbidden)
        assert not is_forbidden("curl localhost:11434", forbidden)

    def test_execute_runbook_blocks_forbidden(self) -> None:
        """Test: OpenClaw bloquea comandos prohibidos del runbook."""
        runbook_with_forbidden = {
            "commands": {
                "test_svc": {
                    "repair": ["rm -rf /"],
                    "timeout_after_repair": 5,
                },
            },
            "forbidden_commands": ["rm -rf"],
        }

        result = execute_runbook_action(
            "test_svc",
            runbook_with_forbidden["commands"]["test_svc"],
            runbook_with_forbidden,
        )
        assert result == "blocked"

    def test_execute_runbook_runs_safe_commands(self) -> None:
        """Test: OpenClaw ejecuta comandos seguros del runbook."""
        safe_action = {
            "repair": ["echo 'repairing'"],
            "timeout_after_repair": 5,
        }
        safe_runbook = {"forbidden_commands": ["rm -rf"]}

        with patch("monitor.openclaw.run_command", return_value=(True, "repairing")):
            result = execute_runbook_action("test_svc", safe_action, safe_runbook)
            assert result == "ok"

    def test_process_emergency_ignores_healthy_services(self) -> None:
        """Test: OpenClaw ignora servicios saludables en emergencia."""
        state = {
            "status": "CRITICAL",
            "services": {
                "ollama": {"ok": True},
                "network": {"ok": False},
            },
        }

        with patch("monitor.openclaw.execute_runbook_action") as mock_exec:
            process_emergency(state, self.test_runbook)
            # Solo network debería ser procesado (ollama está OK)
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert call_args[0] == "network"

    def test_process_emergency_alerts_unknown_services(self) -> None:
        """Test: OpenClaw alerta si un servicio caído no está en runbook."""
        state = {
            "status": "CRITICAL",
            "services": {
                "unknown_svc": {"ok": False},
            },
        }

        with patch("monitor.openclaw.execute_runbook_action") as mock_exec:
            process_emergency(state, self.test_runbook)
            # unknown_svc no está en runbook, no debería ejecutarse
            mock_exec.assert_not_called()

    def test_dead_man_timeout_constant(self) -> None:
        """Test: dead-man timeout es 60 segundos."""
        assert DEAD_MAN_TIMEOUT == 60

    def test_stats_file_writing(self) -> None:
        """Test: stats se escriben en formato JSON válido."""
        from monitor.openclaw import save_stats, stats

        stats["activations"] = 1
        stats["last_activation"] = "2026-06-03T18:00:00"

        with patch("monitor.openclaw.STATS_FILE", self.test_stats):
            save_stats()
            assert self.test_stats.exists()
            loaded = json.loads(self.test_stats.read_text())
            assert loaded["activations"] == 1


class TestOpenClawIntegration(unittest.TestCase):
    """Tests de integración: simular caída de red + verificación runbook."""

    def setUp(self) -> None:
        """Setup: state file de emergencia simulada."""
        self.test_state = Path("/tmp/ura_snc_state_integration.json")  # noqa: S108
        self.emergency_state = {
            "timestamp": "2026-06-03T18:00:00",
            "status": "CRITICAL",
            "services": {
                "network": {
                    "ok": False,
                    "check": "ip link show enP7s7 | grep -q UP",
                    "repair_result": "escalated",
                },
                "ollama": {
                    "ok": True,
                    "check": "curl -sf http://localhost:11434/api/tags",
                },
                "model_router": {
                    "ok": True,
                    "check": "curl -sf http://localhost:11435/health",
                },
            },
            "openclaw_active": True,
            "repair_attempts": {"network": 3},
        }
        self.test_state.write_text(json.dumps(self.emergency_state))

    def tearDown(self) -> None:
        if self.test_state.exists():
            self.test_state.unlink()

    def test_simulated_network_failure_opens_runbook(self) -> None:
        """TEST CLAVE: Simular caída de red → OpenClaw lee EMERGENCY → abre runbook."""
        # 1. Verificar que el state file simula una caída de red
        state = json.loads(self.test_state.read_text())
        assert state["status"] == "CRITICAL"
        assert not state["services"]["network"]["ok"]

        # 2. Verificar que OpenClaw detecta la emergencia
        assert is_emergency(state)

        # 3. Verificar que el runbook tiene el servicio network
        runbook = load_runbook()
        assert "network" in runbook.get("commands", {})

        # 4. Verificar que OpenClaw puede procesar la emergencia
        with patch("monitor.openclaw.run_command", return_value=(True, "ok")):  # noqa: SIM117
            with patch("monitor.openclaw.execute_runbook_action") as mock_exec:
                process_emergency(state, runbook)
                # Network debería ser procesado
                assert mock_exec.called

    def test_openclaw_does_not_act_without_emergency(self) -> None:
        """TEST: OpenClaw NO se activa si el sistema está OK."""
        ok_state = {
            "timestamp": "2026-06-03T18:00:00",
            "status": "OK",
            "services": {"network": {"ok": True}},
            "openclaw_active": False,
        }

        with patch("monitor.openclaw.run_command"):  # noqa: SIM117
            with patch("monitor.openclaw.execute_runbook_action") as mock_exec:
                # No debería ejecutarse nada
                if is_emergency(ok_state):
                    process_emergency(ok_state, load_runbook())
                mock_exec.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
