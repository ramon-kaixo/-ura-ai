#!/usr/bin/env python3
"""Sistema Nervioso Central (SNC) — Polling activo cada 10s.
Monitoriza procesos vía HTTP/socket, escribe estado en ~/.ura/run/ura_snc_state.json.
Ejecuta emergency_runbook.json ante fallos. Autónomo, sin dependencia de red.
Incluye: error_logger (log circular), mac_heartbeat (detección Mac).
Modo Soberanía: GX10 opera independientemente del Mac.
"""

import sys
from pathlib import Path


import json
import os
import platform
import shlex
import signal
import subprocess
import threading
import time
from datetime import UTC, datetime

# Módulos locales (misma carpeta)
from error_logger import ErrorLogger
from mac_heartbeat import MacHeartbeat
# notifier está en core/, se importa bajo demanda para evitar circular imports

# Autosuficiente: carga system_config.json directamente (no depende de config_manager)
_config_path = Path(__file__).parent.parent / "config" / "system_config.json"
_raw_config = json.loads(_config_path.read_text()) if _config_path.exists() else {}
_system = platform.system().lower()
if _system == "linux":
    _host = platform.node().lower()
    _profile_key = "linux_asus" if any(h in _host for h in ("gx10", "gx10-64c3", "asus")) else "linux_terminal"
else:
    _profile_key = "darwin_mac"
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

# Umbrales de activación de la tuneladora
UMBRALES = {
    "criticos": ["ollama", "ura-openclaw", "qdrant", "model-router", "tailscaled"],
    "max_fallos_criticos": 2,
    "max_fallos_totales": 4,
    "cpu_bucle_umbral": 80.0,
    "opencode_cpu_umbral": 80.0,
    "opencode_ciclos_confirmar": 2,
}
_CPU_DETECTION_ENABLED: bool = False
_BUCLE_TIMEOUT: float = 30.0
_pending_sigcont: dict[int, str] = {}
_pending_lock = threading.Lock()
_anomalias: list[dict] = []
_opencode_ciclos_alta: int = 0

# Instancias globales
error_logger = ErrorLogger()
mac_heartbeat = MacHeartbeat()

def _notify(msg: str, level: str = "warning") -> None:
    """Wrapper lazy de core/notifier.notify para evitar circular imports."""
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.notifier import notify as _n
        _n(msg, level=level)
    except Exception as e:
        error_logger.log_error(context="SNC", gateway_status="NOTIFY_FAIL", severity="WARN", message=f"notify: {e}")

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
        needs_shell = any(op in cmd for op in ['|', '&&', '||', ';', '$('])
        if needs_shell:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                executable='/bin/bash',
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
            ["ssh", "-o", "ConnectTimeout=2", os.environ.get("TERMINAL_SSH", "ramon@10.164.1.26"), remote_cmd],
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
        pass

    return False


def poll_services(runbook: dict) -> dict:
    """Polling de todos los servicios. Retorna dict de estado.
    Modo Soberanía: GX10 opera independientemente.
    """
    global openclaw_active, openclaw_stable_since, repair_attempts

    state = {
        "timestamp": datetime.now(UTC).isoformat(),
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
                # Fallback: intentar vía Tailscale (desde config)
                _mac_ts = _profile.get("terminal", {}).get("tailscale_ip", "100.123.81.101")
                ts_ok, _ = run_command(f"ping -c 1 -W 2 {_mac_ts}", timeout=3)
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
    state = {"timestamp": datetime.now(UTC).isoformat(), "status": "SHUTDOWN", "services": {}}
    write_state(state)
    PID_FILE.unlink(missing_ok=True)
    sys.exit(0)


# ─── Detección de anomalías en caliente ─────────────────────

def check_zombies() -> list[int]:
    """Procesos zombie (estado Z) → kill -KILL directo."""
    zombies = []
    for pid in Path("/proc").iterdir():
        if not pid.name.isdigit():
            continue
        status_file = pid / "status"
        if not status_file.exists():
            continue
        try:
            for line in status_file.read_text(errors="replace").splitlines():
                if line.startswith("State:") and "Z" in line:
                    zombies.append(int(pid.name))
                    break
        except (OSError, PermissionError):
            continue
    return zombies


def check_bucle_cpu(umbral: float = UMBRALES["cpu_bucle_umbral"]) -> list[tuple[int, str, float]]:
    """Procesos Python/node con CPU INSTANTÁNEA > umbral (usa ps, no /proc/stat acumulado)."""
    import subprocess
    result: list[tuple[int, str, float]] = []
    try:
        out = subprocess.run(
            ["ps", "aux", "--sort=-%cpu"],
            capture_output=True, text=True, timeout=5,
        )
        for line in out.stdout.splitlines()[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            try:
                cpu = float(parts[2])
            except ValueError:
                continue
            if cpu < umbral:
                continue
            comm = parts[10][:30]
            if not any(x in comm for x in ("python", "node", "ruff", "ollama")):
                continue
            pid = int(parts[1])
            result.append((pid, comm, round(cpu, 1)))
    except Exception:
        pass
    return result[:10]


def check_opencode_colgado() -> bool:
    """Detecta si OpenCode está congelado (CPU alta + sin respuesta).
    Busca el binario exacto 'opencode' (no -f parcial) para evitar falsos positivos.
    """
    try:
        pid = subprocess.run(
            ["pgrep", "-x", "opencode"], capture_output=True, text=True, timeout=5,
        )
        if not pid.stdout.strip():
            return False
        cpu = subprocess.run(
            ["ps", "-p", pid.stdout.strip(), "-o", "%cpu="],
            capture_output=True, text=True, timeout=5,
        )
        return float(cpu.stdout.strip()) > UMBRALES["opencode_cpu_umbral"]
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return False


def _limpiar_zombies() -> None:
    zombies = check_zombies()
    for pid in zombies:
        try:
            os.kill(pid, signal.SIGKILL)
            log_msg = f"💀 Zombie eliminado: PID {pid}"
            print(log_msg)
            error_logger.log_error(context="SNC", gateway_status="ZOMBIE_KILLED", severity="WARN", message=log_msg)
        except (OSError, PermissionError):
            pass


def _sigcont_seguro(pid: int, nombre_original: str) -> None:
    """SIGCONT solo si el PID sigue detenido y no se recicló."""
    with _pending_lock:
        stored = _pending_sigcont.get(pid)
        if stored is None:
            return
        if stored != nombre_original:
            _pending_sigcont.pop(pid, None)
            return
    try:
        status = Path(f"/proc/{pid}/status")
        if not status.exists():
            with _pending_lock:
                _pending_sigcont.pop(pid, None)
            return
        lines = status.read_text(errors="replace").splitlines()
        state = name = ""
        for line in lines:
            if line.startswith("State:"):
                state = line.split(":", 1)[1].strip()
            elif line.startswith("Name:"):
                name = line.split(":", 1)[1].strip()
        if "T" not in state or name != nombre_original:
            with _pending_lock:
                _pending_sigcont.pop(pid, None)
            return
        os.kill(pid, signal.SIGCONT)
    except (OSError, PermissionError, ProcessLookupError):
        pass
    with _pending_lock:
        _pending_sigcont.pop(pid, None)


def _aislar_bucle(pid: int, nombre: str, cpu: float) -> None:
    """Aísla un proceso en bucle: SIGSTOP + volcado /proc."""
    with _pending_lock:
        if pid in _pending_sigcont:
            return
        _pending_sigcont[pid] = nombre
    sandbox_dir = Path(f"/tmp/ura_aislados/{pid}")
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.kill(pid, signal.SIGSTOP)
        threading.Timer(_BUCLE_TIMEOUT, _sigcont_seguro, args=[pid, nombre]).start()
        # Volcar información del proceso
        for subdir in ("status", "maps", "fd", "wchan"):
            src = Path(f"/proc/{pid}/{subdir}")
            if src.exists():
                try:
                    dst = sandbox_dir / subdir
                    if src.is_dir():
                        import shutil
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        dst.write_text(src.read_text(errors="replace"))
                except (OSError, PermissionError):
                    pass
        (sandbox_dir / "nombre.txt").write_text(nombre)
        (sandbox_dir / "cpu.txt").write_text(f"{cpu}%")
        msg = f"🧊 Aislado: {nombre} PID {pid} ({cpu}% CPU)"
        print(msg)
        _notify(msg, level="critical")
    except (OSError, PermissionError) as e:
        msg = f"Error aislando {nombre} PID {pid}: {e}"
        error_logger.log_error(context="SNC", gateway_status="ISOLATE_FAIL", severity="WARN", message=msg)


def _check_umbrales(state: dict) -> bool:
    """Retorna True si se deben activar medidas correctivas."""
    servicios = state.get("services", {})
    criticos_caidos = sum(
        1 for s in UMBRALES["criticos"]
        if servicios.get(s, {}).get("ok") is False
    )
    totales_caidos = sum(
        1 for s in servicios.values()
        if s.get("ok") is False
    )
    return criticos_caidos >= UMBRALES["max_fallos_criticos"] or totales_caidos >= UMBRALES["max_fallos_totales"]


def _trigger_tuneladora() -> None:
    """Activa el ciclo de mantenimiento de la tuneladora ahora."""
    try:
        subprocess.run(["systemctl", "start", "ura-maintenance.service"], timeout=30)
        _notify("🔧 Tuneladora activada por detección de anomalía", level="warning")
    except subprocess.TimeoutExpired:
        _notify("⚠️ Tuneladora no respondió en 30s", level="critical")
    except Exception as e:
        _notify(f"⚠️ Error activando tuneladora: {e}", level="warning")


def main() -> None:
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    PID_FILE.write_text(str(os.getpid()))

    runbook = load_runbook()
    if runbook.get("version") == "0":
        sys.exit(1)


    try:
        _last_notification: float = 0
        _notify_cooldown: float = 300.0  # 5 min entre notificaciones

        while True:
            state = poll_services(runbook)
            write_state(state)

            # ─── Anomalías en caliente ───
            # 1. Zombies → matar directo
            _limpiar_zombies()

            # 2. Bucles CPU → DESACTIVADO (_CPU_DETECTION_ENABLED=False):
            #    check_bucle_cpu usa CPU acumulada, no delta.
            #    Causaba SIGSTOP eterno a model-router y otros procesos longevos.
            #    Pendiente: implementar con delta (/proc/stat snapshots entre ciclos).
            if _CPU_DETECTION_ENABLED:
                for pid, nombre, cpu in check_bucle_cpu():
                    _aislar_bucle(pid, nombre, cpu)

            # 3. OpenCode colgado → contar ciclos, aislar si persiste
            if check_opencode_colgado():
                _opencode_ciclos_alta += 1
                if _opencode_ciclos_alta >= UMBRALES["opencode_ciclos_confirmar"]:
                    _aislar_bucle(0, "opencode", UMBRALES["opencode_cpu_umbral"])
                    _opencode_ciclos_alta = 0
            else:
                _opencode_ciclos_alta = 0

            # 4. Umbrales → activar tuneladora si es necesario
            if _check_umbrales(state):
                _trigger_tuneladora()

            # Notificar si estado crítico
            if state.get("status") == "CRITICAL":
                now = time.time()
                if now - _last_notification > _notify_cooldown:
                    failed = [s for s, v in state.get("services", {}).items() if v.get("status") != "OK"]
                    msg = f"SNC detectó {len(failed)} servicios con fallo: {', '.join(failed[:5])}"
                    _notify(msg, level="critical")
                    _last_notification = now

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
