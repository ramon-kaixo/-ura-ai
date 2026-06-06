"""Action Handler — Ejecuta comandos del Model Broker con whitelist.

Recibe comandos del ai_broker, valida contra whitelist,
ejecuta con logging obligatorio en logs/infra_actions.log.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("infra.handler")
ALERTS_LOG = Path(__file__).parent.parent.parent / "logs" / "infra_actions.log"

# Whitelist de comandos permitidos (FSM output)
COMMAND_WHITELIST = {
    "turbo": lambda: _change_mode("TURBO"),
    "eco": lambda: _change_mode("ECO"),
    "auto": lambda: _change_mode("AUTO"),
    "restart_router": lambda: _systemctl("restart", "model-router"),
    "flush_logs": lambda: _flush_logs(),
    "alert": lambda: _write_alert("Alerta automática del Model Broker"),
    "maintenance": lambda: _run_maintenance(),
}

_ACTION_LOG: list[dict] = []


def _change_mode(mode: str) -> dict:
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:11435/power_mode?mode={mode}", method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _systemctl(action: str, service: str) -> dict:
    r = subprocess.run(["systemctl", action, service], capture_output=True, text=True, timeout=30)
    return {"rc": r.returncode, "stdout": r.stdout.strip()}


def _flush_logs() -> dict:
    import shutil
    log_dir = Path(__file__).parent.parent.parent / "logs"
    rotated = 0
    for f in log_dir.glob("*.log"):
        if f.stat().st_size > 10_000_000:  # 10MB
            shutil.copy2(f, str(f) + ".old")
            f.write_text("")
            rotated += 1
    return {"rotated": rotated}


def _write_alert(msg: str) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_LOG, "a") as f:
        f.write(entry + "\n")
    return {"logged": True, "entry": entry}


def _run_maintenance() -> dict:
    r = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent.parent / "scripts/chaos_maintenance.py")],
        capture_output=True, text=True, timeout=180,
    )
    return {"rc": r.returncode, "output": r.stdout[-300:]}


async def execute_action(action: str) -> dict:
    """Ejecuta un comando si está en la whitelist. Retorna resultado."""
    ts = datetime.now(timezone.utc).isoformat()

    if action not in COMMAND_WHITELIST:
        result = {"action": action, "status": "rejected", "reason": "not in whitelist", "ts": ts}
        log.warning("infra.handler: comando rechazado: %s", action)
        _ACTION_LOG.append(result)
        return result

    try:
        handler = COMMAND_WHITELIST[action]
        response = handler()
        result = {"action": action, "status": "executed", "response": response, "ts": ts}
        log.info("infra.handler: %s → OK", action)
    except Exception as e:
        result = {"action": action, "status": "error", "error": str(e), "ts": ts}
        log.warning("infra.handler: %s → error: %s", action, e)

    # Log obligatorio
    ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_LOG, "a") as f:
        f.write(json.dumps(result) + "\n")

    _ACTION_LOG.append(result)
    return result


def get_handler_status() -> dict:
    return {
        "whitelist": sorted(COMMAND_WHITELIST.keys()),
        "actions_executed": len(_ACTION_LOG),
        "last_actions": _ACTION_LOG[-5:] if _ACTION_LOG else [],
    }
