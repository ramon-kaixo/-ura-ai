#!/usr/bin/env python3
"""OpenClaw — Brazo ejecutor de emergencia bajo control del SNC.

NO es un agente autónomo. Es un intérprete del emergency_runbook.json.
Solo se activa cuando snc.py marca STATE_EMERGENCY.
Si una incidencia no está en el runbook → bloqueo + ALERTA al administrador.

Protocolo de "Hombre Muerto": timeout de 60s sin confirmación humana
→ no ejecuta acciones destructivas por defecto.

Lee estado de: /tmp/ura_snc_state.json (escrito por snc.py)
Registra acciones en: stats.json (Perfil A de memoria)
"""

import sys
from pathlib import Path


import json
import os
import shlex
import signal
import subprocess
import time
from datetime import UTC, datetime

# Paths
_STATE_DIR = Path.home() / ".ura" / "run"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_STATE_DIR.chmod(0o700)
STATE_FILE = _STATE_DIR / "ura_snc_state.json"
RUNBOOK_PATH = Path(__file__).parent.parent / "deploy" / "emergency_runbook.json"
STATS_FILE = _STATE_DIR / "ura_openclaw_stats.json"
PID_FILE = _STATE_DIR / "ura_openclaw.pid"

# Configuración determinista
POLL_INTERVAL = 5  # segundos entre checks del state file
DEAD_MAN_TIMEOUT = 60  # segundos sin confirmación humana → bloqueo
CONFIRMATION_SCRIPT = Path(__file__).parent.parent / "deploy" / "claw_listener.sh"

# Estados del SNC que activan OpenClaw
EMERGENCY_STATES = {"CRITICAL", "EMERGENCY"}

# Contador de stats
stats = {
    "activations": 0,
    "actions_executed": 0,
    "actions_blocked": 0,
    "human_confirmations": 0,
    "dead_man_triggers": 0,
    "last_activation": None,
    "last_action": None,
}


def load_runbook() -> dict:
    """Carga el runbook de emergencia. Solo intérprete, no decide."""
    try:
        return json.loads(RUNBOOK_PATH.read_text())
    except Exception:
        return {"version": "0", "commands": {}, "retry_policy": {}, "forbidden_commands": []}


def load_state() -> dict:
    """Lee el state file escrito por snc.py. No lee estados legacy."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {"status": "UNKNOWN", "services": {}, "openclaw_active": False}


def save_stats() -> None:
    """Registra stats en stats.json (Perfil A de memoria)."""
    try:
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(stats, indent=2))
        os.replace(str(tmp), str(STATS_FILE))
    except Exception:
        pass


def is_emergency(state: dict) -> bool:
    """Determina si el estado del sistema es una emergencia."""
    return state.get("status") in EMERGENCY_STATES


def is_forbidden(cmd: str, forbidden: list) -> bool:
    """Verifica que un comando no esté en la lista prohibida."""
    cmd_lower = cmd.lower()
    return any(f.lower() in cmd_lower for f in forbidden)


def run_command(cmd: str, timeout: int = 10) -> tuple[bool, str]:
    """Ejecuta un comando de forma segura sin shell=True.
    Retorna (éxito, output).
    """
    try:
        args = shlex.split(cmd)
        result = subprocess.run(
            args, shell=False, capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def request_human_confirmation(reason: str) -> bool:
    """Solicita confirmación humana via claw_listener en Mac.
    Retorna True si confirmado, False si cancelado o timeout.
    """
    if not CONFIRMATION_SCRIPT.exists():
        return False

    try:
        result = subprocess.run(
            ["bash", str(CONFIRMATION_SCRIPT), "OPENCLAW_ALERT", reason],
            capture_output=True, text=True, timeout=DEAD_MAN_TIMEOUT,
        )
        confirmed = "CONFIRMADO" in result.stdout
        if confirmed:
            stats["human_confirmations"] += 1
            save_stats()
        return confirmed
    except subprocess.TimeoutExpired:
        stats["dead_man_triggers"] += 1
        save_stats()
        return False
    except Exception:
        return False


def execute_runbook_action(service_name: str, action: dict, runbook: dict) -> str:
    """Ejecuta una acción del runbook. Solo intérprete, no decide.
    Retorna 'ok', 'blocked', 'failed', 'no_human_confirm'.
    """
    repair_cmds = action.get("repair", [])
    forbidden = runbook.get("forbidden_commands", [])

    if not repair_cmds:
        return "no_repair_defined"

    for cmd in repair_cmds:
        if is_forbidden(cmd, forbidden):
            stats["actions_blocked"] += 1
            save_stats()
            return "blocked"

        # Para acciones destructivas, solicitar confirmación humana
        destructive_keywords = ["reboot", "shutdown", "restart", "poweroff", "halt"]
        is_destructive = any(kw in cmd.lower() for kw in destructive_keywords)

        if is_destructive and not request_human_confirmation(f"OpenClaw solicita confirmación para: {cmd}"):
            stats["actions_blocked"] += 1
            save_stats()
            return "no_human_confirm"

        ok, output = run_command(cmd, timeout=action.get("timeout_after_repair", 10))
        stats["actions_executed"] += 1
        stats["last_action"] = {
            "service": service_name,
            "command": cmd,
            "success": ok,
            "output": output[:200],
            "timestamp": datetime.now(UTC).isoformat(),
        }
        save_stats()

        if ok:
            return "ok"

    return "failed"


def process_emergency(state: dict, runbook: dict) -> None:
    """Procesa una emergencia: ejecuta runbook para servicios caídos.
    NO toma decisiones propias. Solo interpreta el runbook.
    """
    services = state.get("services", {})
    runbook.get("forbidden_commands", [])

    for svc_name, svc_state in services.items():
        if svc_state.get("ok"):
            continue

        # Servicio caído — buscar en runbook
        svc_config = runbook.get("commands", {}).get(svc_name)
        if not svc_config:
            stats["actions_blocked"] += 1
            save_stats()
            continue

        # Ejecutar reparación del runbook
        execute_runbook_action(svc_name, svc_config, runbook)


def handle_signal(sig, frame) -> None:
    """Manejo de señales para cierre limpio."""
    PID_FILE.unlink(missing_ok=True)
    save_stats()
    sys.exit(0)


def main() -> None:
    """Loop principal: lee state file, activa en emergencia, ejecuta runbook."""
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    PID_FILE.write_text(str(os.getpid()))

    runbook = load_runbook()
    if runbook.get("version") == "0":
        sys.exit(1)


    try:
        while True:
            state = load_state()

            if is_emergency(state):
                if stats["activations"] == 0 or stats["last_activation"] is None:
                    stats["activations"] += 1
                    stats["last_activation"] = datetime.now(UTC).isoformat()
                    save_stats()

                process_emergency(state, runbook)
            # Standby mode — sin consumo de recursos extra
            elif stats["activations"] > 0 and stats["last_activation"]:
                stats["last_activation"] = None
                save_stats()

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        PID_FILE.unlink(missing_ok=True)
        save_stats()


if __name__ == "__main__":
    main()
