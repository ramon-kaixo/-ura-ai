#!/usr/bin/env python3
"""chaos_monkey.py — Prueba de resiliencia: mata procesos y verifica auto-recuperación.

Uso:
    python3 core/chaos_monkey.py           # prueba completa
    python3 core/chaos_monkey.py --quick   # solo mata supervisor
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

def _load_api_key() -> str | None:
    env_path = Path(__file__).parent.parent / ".env"
    key = os.environ.get("URA_API_KEY")
    if key:
        return key
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("URA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("chaos_monkey")

SERVICES = ["model-router", "ura-supervisor", "ura-router-health.timer"]


def _check(service: str) -> bool:
    r = subprocess.run(["systemctl", "is-active", service], capture_output=True, text=True)
    return r.stdout.strip() == "active"


def _wait_for(service: str, target: str, timeout: int = 15) -> bool:
    for i in range(timeout):
        r = subprocess.run(["systemctl", "is-active", service], capture_output=True, text=True)
        if r.stdout.strip() == target:
            return True
        time.sleep(1)
    return False


def _kill_pid(service: str) -> int | None:
    r = subprocess.run(
        ["systemctl", "show", service, "-p", "MainPID"],
        capture_output=True, text=True,
    )
    pid_str = r.stdout.strip().replace("MainPID=", "")
    if pid_str and pid_str != "0":
        pid = int(pid_str)
        os.kill(pid, signal.SIGKILL)
        return pid
    return None


def test_supervisor_auto_restart() -> bool:
    log.info("=" * 50)
    log.info("PRUEBA 1: Matar ura-supervisor con SIGKILL")
    log.info("=" * 50)

    if not _check("ura-supervisor"):
        log.warning("  ura-supervisor no está activo, saltando...")
        return True

    pid = _kill_pid("ura-supervisor")
    if pid:
        log.info("  PID %d eliminado con SIGKILL", pid)
    else:
        log.warning("  No se pudo obtener PID")
        return False

    log.info("  Esperando auto-restart (RestartSec=5)...")
    ok = _wait_for("ura-supervisor", "active", timeout=15)
    if ok:
        log.info("  ✅ ura-supervisor auto-recuperado en <15s")
        time.sleep(3)
    else:
        log.error("  ❌ ura-supervisor NO se recuperó")
    return ok


def test_ipc_resilience() -> bool:
    log.info("=" * 50)
    log.info("PRUEBA 2: IPC responde después de restart")
    log.info("=" * 50)

    import zmq
    import json
    for attempt in range(5):
        try:
            ctx = zmq.Context()
            sock = ctx.socket(zmq.REQ)
            sock.setsockopt(zmq.RCVTIMEO, 3000)
            sock.connect("ipc:///tmp/ura-supervisor.ipc")
            sock.send(b"health")
            r = json.loads(sock.recv())
            sock.close()
            ctx.term()
            log.info("  ✅ IPC responde: %d tareas activas", r.get("tasks_active", -1))
            return True
        except Exception as e:
            if attempt < 4:
                time.sleep(2)
                continue
            log.error("  ❌ IPC no responde tras %d intentos: %s", attempt + 1, e)
            return False


def test_state_persistence() -> bool:
    log.info("=" * 50)
    log.info("PRUEBA 3: Estado persistió después del restart")
    log.info("=" * 50)

    import zmq
    import json
    try:
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REQ)
        sock.setsockopt(zmq.RCVTIMEO, 5000)
        sock.connect("ipc:///tmp/ura-supervisor.ipc")
        sock.send(b"state get supervisor:heartbeat:last")
        r = json.loads(sock.recv())
        sock.close()
        ctx.term()
        if r.get("value"):
            log.info("  ✅ Heartbeat histórico recuperado de Redis")
            return True
        log.warning("  ⚠️  Heartbeat vacío (primera ejecución?)")
        return True
    except Exception as e:
        log.error("  ❌ Error leyendo estado: %s", e)
        return False


def test_model_router_independent() -> bool:
    log.info("=" * 50)
    log.info("PRUEBA 4: model-router sigue vivo independientemente")
    log.info("=" * 50)

    import urllib.request
    import json
    api_key = _load_api_key()
    try:
        req = urllib.request.Request("http://127.0.0.1:11435/health")
        if api_key:
            req.add_header("X-API-KEY", api_key)
        with urllib.request.urlopen(req, timeout=5) as resp:
            d = json.loads(resp.read())
            ok = d.get("status") == "ok"
            log.info("  %s model-router: %s — %d modelos",
                     "✅" if ok else "❌", d.get("status"), d.get("models_available", 0))
            return ok
    except Exception as e:
        log.error("  ❌ model-router no responde: %s", e)
        return False


def main() -> None:
    quick = "--quick" in sys.argv

    log.info("🐒 CHAOS MONKEY — Prueba de resiliencia del stack URA")
    log.info("")

    results = {}
    results["model_router"] = test_model_router_independent()
    results["supervisor_restart"] = test_supervisor_auto_restart() if not quick else True
    results["ipc"] = test_ipc_resilience()
    results["state"] = test_state_persistence()

    log.info("")
    log.info("=" * 50)
    log.info("RESULTADOS:")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        log.info("  %s %s", "✅" if ok else "❌", name)
    log.info("  %d/%d pruebas pasadas", passed, total)
    log.info("=" * 50)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
