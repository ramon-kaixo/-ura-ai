#!/usr/bin/env python3
"""Sistema Nervioso Central (SNC) — Polling activo cada 10s.
Monitoriza procesos vía HTTP/socket, escribe estado en ~/.ura/run/ura_snc_state.json.
Ejecuta emergency_runbook.json ante fallos. Autónomo, sin dependencia de red.
Incluye: error_logger (log circular), mac_heartbeat (detección Mac).
Modo Soberanía: GX10 opera independientemente del Mac.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
import platform
import shlex
import signal
import subprocess
import time
from datetime import datetime

# Módulos locales (misma carpeta)
sys.path.insert(0, str(Path(__file__).parent))
from error_logger import ErrorLogger
from mac_heartbeat import MacHeartbeat

# Autosuficiente: carga system_config.json directamente (no depende de config_manager)
_config_path = Path(__file__).parent.parent / "config" / "system_config.json"
_raw_config = json.loads(_config_path.read_text()) if _config_path.exists() else {}
_system = platform.system().lower()
_profile_key = "linux_asus" if _system == "linux" else "darwin_mac"
_profile = _raw_config.get("profiles", {}).get(_profile_key, {})
CONFIG = {**_raw_config.get("global_defaults", {}), **_profile}

RUNBOOK_PATH = Path(__file__).parent.parent / "deploy" / "emergency_runbook.json"
_STATE_DIR = Path.home() / ".ura" / "run"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_STATE_DIR.chmod(0o700)
STATE_FILE = _STATE_DIR / "ura_snc_state.json"
PID_FILE = _STATE_DIR / "ura_snc.pid"
POLL_INTERVAL = 10  # segundos
CRITICAL_TIMEOUT = 30  # segundos sin update → CRITICAL

# Instancias globales
error_logger = ErrorLogger()
mac_heartbeat = MacHeartbeat()

openclaw_active = False
openclaw_stable_since = None
repair_attempts: dict[str, int] = {}

# ============================================================
# MODO SOBERANÍA: GX10 opera independientemente
# Si Mac cae, GX10 continúa sin interrupciones ni avisos.
# El estado mac_connection_ok se actualiza automáticamente.
# ============================================================


def load_runbook() -> dict:
    try:
        return json.loads(RUNBOOK_PATH.read_text())
    except Exception as e:
        error_logger.log_error(
            context="SNC",
            gateway_status="RUNBOOK_LOAD_FAIL",
            severity="CRIT",
            message=f"Error cargando runbook: {e}",
        )
        return {"version": "0", "commands": {}, "retry_policy": {}}


def run_command(cmd: str, timeout: int = 10) -> tuple[bool, str]:
    """Ejecuta un comando. Usa shell=True solo si hay operadores shell.
    Excepción documentada: los comandos vienen del runbook whitelist (no input usuario).
    """
    try:
        needs_shell = any(op in cmd for op in ["|", "&&", "||", ";", "$("])
        if needs_shell:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                executable="/bin/bash",
            )
        else:
            args = shlex.split(cmd)
            result = subprocess.run(
                args, shell=False, capture_output=True, text=True, timeout=timeout,
            )
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def check_service(check_cmd: str) -> bool:
    """Verifica un servicio ejecutando su comando de check."""
    if not check_cmd:
        return True
    ok, _ = run_command(check_cmd, timeout=5)
    return ok


def is_command_forbidden(cmd: str, forbidden: list) -> bool:
    """Verifica que un comando no esté en la lista prohibida."""
    cmd_lower = cmd.lower()
    return any(f.lower() in cmd_lower for f in forbidden)


def repair_service(service_name: str, config: dict, runbook: dict) -> str:
    """Intenta reparar un servicio. Retorna 'ok', 'failed', 'escalated'."""
    global repair_attempts, openclaw_active

    max_attempts = config.get("max_repair_attempts", runbook["retry_policy"]["max_attempts"])
    repair_cmds = config.get("repair", [])
    forbidden = runbook.get("forbidden_commands", [])

    if not repair_cmds:
        return "no_repair_defined"

    current = repair_attempts.get(service_name, 0)
    if current >= max_attempts:
        return "escalated"

    attempt = current + 1
    repair_attempts[service_name] = attempt

    for cmd in repair_cmds:
        if is_command_forbidden(cmd, forbidden):
            continue

        ok, _output = run_command(cmd, timeout=config.get("timeout_after_repair", 10))
        if ok:
            repair_attempts[service_name] = 0
            return "ok"

    return "failed"


def check_mac_unauthorized_writes() -> bool:
    """Detecta intentos de escritura no autorizados en Mac.
    Retorna True si detecta actividad sospechosa.
    """
    # Verificar si hay archivos .py recién modificados en Mac
    # (esto solo funciona si Mac es alcanzable)
    if not mac_heartbeat.is_mac_connected():
        return False

    try:
        remote_cmd = "ps aux | grep -E 'vim|nano|emacs|code' | grep -v grep"
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=2", "ramon@10.164.1.26", remote_cmd],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            error_logger.log_error(
                context="MAC",
                gateway_status="UNAUTHORIZED_WRITE",
                severity="CRIT",
                message=f"Intento de escritura detectado en Mac: {result.stdout.strip()[:100]}",
            )
            return True
    except Exception as e:
        error_logger.log_error(
            context="MAC",
            gateway_status="UNAUTHORIZED_WRITE_CHECK_FAIL",
            severity="WARN",
            message=f"Error verificando escrituras no autorizadas: {e}",
        )

    return False


def poll_services(runbook: dict) -> dict:
    """Polling de todos los servicios. Retorna dict de estado.
    Modo Soberanía: GX10 opera independientemente.
    """
    global openclaw_active, openclaw_stable_since, repair_attempts

    state = {
        "timestamp": datetime.now().isoformat(),
        "status": "OK",
        "services": {},
        "openclaw_active": openclaw_active,
        "mac_connected": mac_heartbeat.is_mac_connected(),
        "mac_connection_ok": mac_heartbeat.is_mac_connected(),
        "sovereignty_mode": True,
        "repair_attempts": dict(repair_attempts),
    }

    all_ok = True

    for svc_name, svc_config in runbook.get("commands", {}).items():
        # Servicio especial: mac_reachability (multi-path Ethernet→Tailscale)
        if svc_name == "mac_reachability":
            mac_ok = mac_heartbeat.check_mac()
            if not mac_ok:
                # Fallback: intentar vía Tailscale
                ts_ok, _ = run_command("ping -c 1 -W 2 100.123.81.101", timeout=3)
                if ts_ok:
                    mac_ok = True
            state["services"][svc_name] = {
                "ok": mac_ok,
                "consecutive_failures": mac_heartbeat.get_consecutive_failures(),
                "check": "ping Mac (Ethernet→Tailscale)",
            }
            if not mac_ok:
                all_ok = False
                if mac_heartbeat.should_escalate():
                    error_logger.log_error(
                        context="ASUS",
                        gateway_status="DISCONNECTED",
                        severity="WARN",
                        message=f"Mac no alcanzable por Ethernet ni Tailscale. Fallos: {mac_heartbeat.get_consecutive_failures()}.",
                    )
            continue

        # Saltar servicios con dependencia only_if si el padre está ok
        only_if = svc_config.get("only_if", "")
        if only_if:
            parent_ok = state["services"].get(only_if, {}).get("ok", True)
            if parent_ok:
                state["services"][svc_name] = {"ok": True, "check": f"skipped (parent {only_if} ok)", "repair_result": "no_repair_needed"}
                continue

        check_cmd = svc_config.get("check", "")
        ok = check_service(check_cmd)

        svc_state = {"ok": ok, "check": check_cmd[:50]}

        if not ok:
            all_ok = False
            result = repair_service(svc_name, svc_config, runbook)
            svc_state["repair_result"] = result

            # Loggear error
            error_logger.log_error(
                context="ASUS",
                gateway_status="FAIL" if result == "failed" else "REPAIRING",
                severity="CRIT" if result == "escalated" else "WARN",
                message=f"Servicio {svc_name}: {result}",
            )

            if result == "escalated" and svc_config.get("activate_on_emergency") and not openclaw_active:
                openclaw_active = True
                # Lanzar openclaw.py como proceso independiente
                openclaw_script = Path(__file__).parent / "openclaw.py"
                if openclaw_script.exists():
                    proc = subprocess.Popen(
                        [sys.executable, str(openclaw_script)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    # No esperamos a que termine, pero registramos el PID para tracking
                    error_logger.log_error(
                        context="SNC",
                        gateway_status="OPENCLAW_LAUNCHED",
                        severity="INFO",
                        message=f"OpenClaw lanzado con PID {proc.pid}",
                    )

        state["services"][svc_name] = svc_state

    # Detectar escrituras no autorizadas en Mac
    check_mac_unauthorized_writes()

    # Gestión de OpenClaw
    if openclaw_active:
        if all_ok and not openclaw_stable_since:
            openclaw_stable_since = time.time()
        elif not all_ok:
            openclaw_stable_since = None

        if openclaw_stable_since and (time.time() - openclaw_stable_since) >= 30:
            subprocess.run(
                ["pkill", "-TERM", "-f", "openclaw"],
                capture_output=True, text=True, timeout=5,
            )
            openclaw_active = False
            openclaw_stable_since = None

    state["status"] = "OK" if all_ok else "CRITICAL"
    state["openclaw_active"] = openclaw_active
    state["mac_connected"] = mac_heartbeat.is_mac_connected()
    state["mac_connection_ok"] = mac_heartbeat.is_mac_connected()
    state["repair_attempts"] = dict(repair_attempts)

    return state


def write_state(state: dict) -> None:
    """Escribe el estado en /tmp/ura_snc_state.json de forma atómica."""
    try:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        os.replace(str(tmp), str(STATE_FILE))
    except Exception as e:
        error_logger.log_error(
            context="SNC",
            gateway_status="STATE_WRITE_FAIL",
            severity="CRIT",
            message=f"Error escribiendo estado: {e}",
        )


def handle_signal(sig, frame) -> None:
    state = {"timestamp": datetime.now().isoformat(), "status": "SHUTDOWN", "services": {}}
    write_state(state)
    PID_FILE.unlink(missing_ok=True)
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    PID_FILE.write_text(str(os.getpid()))

    runbook = load_runbook()
    if runbook.get("version") == "0":
        sys.exit(1)


    try:
        while True:
            state = poll_services(runbook)
            write_state(state)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
