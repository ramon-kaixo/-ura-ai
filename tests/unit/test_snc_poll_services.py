"""Tests de seguridad para monitor/snc.py::poll_services (C1, Sprint 5b).

Sin red de tests previa, estos tests son el oráculo del refactor.
Deterministas: todo subprocess y heartbeat mockeado, nada toca el sistema.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "monitor"))

import snc


@pytest.fixture
def fake_subprocess(monkeypatch):
    """Captura todos los comandos que poll_services intentaría ejecutar."""
    ejecutados: list[str] = []

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, str):
            ejecutados.append(cmd)
        else:
            ejecutados.append(" ".join(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="active", stderr="")

    monkeypatch.setattr(snc.subprocess, "run", fake_run)
    monkeypatch.setattr(snc.mac_heartbeat, "is_mac_connected", lambda: False)
    monkeypatch.setattr(snc.mac_heartbeat, "get_consecutive_failures", lambda: 0)
    monkeypatch.setattr(snc, "check_mac_unauthorized_writes", lambda: None)
    monkeypatch.setattr(snc.error_logger, "log_error", lambda **_: None)
    return ejecutados


def test_poll_services_nunca_ejecuta_comandos_prohibidos(monkeypatch, fake_subprocess):
    """Invariante de seguridad: comandos peligrosos del runbook nunca se ejecutan."""
    runbook = {
        "retry_policy": {"max_attempts": 3},
        "forbidden_commands": ["rm -rf", "mkfs", "shutdown", "dd if="],
        "commands": {
            "svc1": {"check": "systemctl is-active svc1", "repair": ["echo ok"]},
            "svc2": {"check": "rm -rf /tmp/x", "repair": ["rm -rf /"]},
        },
    }
    state = snc.poll_services(runbook)

    for cmd in fake_subprocess:
        assert "rm " not in cmd
        assert "mkfs" not in cmd
        assert "shutdown" not in cmd
        assert "dd if=" not in cmd

    assert state["status"] in ("OK", "CRITICAL")
    assert "svc1" in state["services"]
    assert "svc2" in state["services"]


def test_poll_services_servicio_sano_no_repara(monkeypatch, fake_subprocess):
    """Servicio cuyo check pasa: ok=True, sin repair_result."""
    runbook = {
        "retry_policy": {"max_attempts": 3},
        "commands": {"svc1": {"check": "systemctl is-active svc1", "repair": ["echo ok"]}},
    }
    state = snc.poll_services(runbook)

    svc = state["services"]["svc1"]
    assert svc["ok"] is True
    assert "repair_result" not in svc
    assert state["status"] == "OK"


def test_poll_services_servicio_caido_intenta_reparar(monkeypatch, fake_subprocess):
    """Servicio cuyo check falla: registra repair_result y estado CRITICAL."""
    real_run = snc.subprocess.run

    def fake_run(cmd, *args, **kwargs):
        ejecutado = cmd if isinstance(cmd, str) else " ".join(cmd)
        fake_subprocess.append(ejecutado)
        rc = 1 if "is-active" in ejecutado else 0
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="")

    monkeypatch.setattr(snc.subprocess, "run", fake_run)
    state = snc.poll_services(
        {
            "retry_policy": {"max_attempts": 3},
            "commands": {"svc1": {"check": "systemctl is-active svc1", "repair": ["echo ok"]}},
        }
    )

    svc = state["services"]["svc1"]
    assert svc["ok"] is False
    assert "repair_result" in svc
    assert state["status"] == "CRITICAL"
