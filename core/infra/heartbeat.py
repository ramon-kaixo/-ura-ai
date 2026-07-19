#!/usr/bin/env python3
"""Heartbeat check para ura-mochila.service.
Reinicia el servicio si /health falla 3 veces consecutivas.

Uso:
  python3 core/infra/heartbeat.py                  # una ejecucion
  python3 core/infra/heartbeat.py --daemon         # bucle cada 30s
"""

import argparse
import json
import logging
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from core.logs.guardian_logger import log_event

STATE_FILE = "/tmp/ura_state.json"  # noqa: S108

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ura.heartbeat")

MOCHILA_URL = "http://127.0.0.1:4098"
HEALTH_PATH = "/health"
MAX_FAILS = 3
CHECK_INTERVAL = 30
_shutdown_flag = False


def check_health() -> bool:
    try:
        req = Request(f"{MOCHILA_URL}{HEALTH_PATH}", method="GET")  # noqa: S310
        with urlopen(req, timeout=5) as resp:  # noqa: S310
            return resp.status == 200
    except (URLError, OSError, ValueError) as e:
        logger.warning("Health check fallo: %s", e)
        return False


def dump_checkpoint() -> None:
    if Path(STATE_FILE).exists():
        try:
            with open(STATE_FILE) as f:  # noqa: PTH123
                cp = json.load(f)
            logger.critical(
                "[HEARTBEAT] Checkpoint pendiente detectado antes de restart: task=%s file=%s",
                cp.get("task_id"),
                cp.get("target_file"),
            )
        except (json.JSONDecodeError, OSError):
            logger.warning("[HEARTBEAT] Checkpoint ilegible, ignorando")


def _save_restart_to_qdrant() -> None:
    try:
        from motor.core.config import UraConfig
        from motor.core.qdrant_client import instancia

        cfg = UraConfig()
        qc = instancia(cfg)
        if qc and qc.disponible:
            qc.guardar_incidente(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "tipo": "ServiceFailure",
                    "subtipo": "heartbeat_restart",
                    "resumen": "ura-mochila.service reiniciado por heartbeat tras 3 fallos consecutivos",
                    "origin_node": "ASUS",
                    "exit_code": -1,
                },
            )
    except Exception:
        logger.exception("Error guardando incidente de reinicio en Qdrant")


def restart_service() -> None:
    dump_checkpoint()
    _save_restart_to_qdrant()
    logger.critical("Reiniciando ura-mochila.service...")
    try:
        res = subprocess.run(
            ["systemctl", "restart", "ura-mochila.service"],  # noqa: S607  -- comando constante
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode == 0:
            logger.info("ura-mochila.service reiniciado exitosamente")
        else:
            logger.error("Fallo restart: %s", res.stderr.strip())
    except subprocess.TimeoutExpired:
        logger.exception("Timeout al reiniciar servicio")
    except FileNotFoundError:
        logger.exception("systemctl no disponible")


vram_critical_cycles = 0
VRAM_PANIC_MB = 22000


def check_vram_pressure() -> None:
    global vram_critical_cycles  # noqa: PLW0603
    cmd = [
        "nvidia-smi",
        "--query-compute-apps=used_memory",
        "--format=csv,noheader,nounits",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)  # noqa: S603  -- comando constante
        total_used = 0
        for line in res.stdout.strip().split("\n"):
            line = line.strip()  # noqa: PLW2901
            if line.isdigit():
                total_used += int(line)

        if total_used > VRAM_PANIC_MB:
            vram_critical_cycles += 1
            log_event(
                "vram_pressure_high",
                model="",
                file="",
                reason="",
                attempts=vram_critical_cycles,
                penalty="",
                sandbox_errors=[],
                complexity=0,
                temperature=0.0,
                result_type="warning",
            )
            logger.warning("VRAM pressure: %d MB used (%d/%d cycles)", total_used, vram_critical_cycles, 3)
            if vram_critical_cycles >= 3:
                log_event(
                    "vram_panic_restart",
                    model="",
                    file="",
                    reason="",
                    attempts=3,
                    penalty="",
                    sandbox_errors=[f"VRAM saturation {total_used} MB > {VRAM_PANIC_MB} MB"],
                    complexity=0,
                    temperature=0.0,
                    result_type="failure",
                )
                logger.critical("VRAM panic: restarting mochila")
                restart_service()
                vram_critical_cycles = 0
        else:
            vram_critical_cycles = 0
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        log_event(
            "vram_monitor_error",
            model="",
            file="",
            reason=str(e),
            attempts=0,
            penalty="",
            sandbox_errors=[],
            complexity=0,
            temperature=0.0,
            result_type="failure",
        )
        logger.warning("VRAM monitor error: %s", e)


def check_loop_latency() -> float:
    async def _measure():
        import time as _t

        t0 = _t.monotonic()
        await asyncio.sleep(0)
        t1 = _t.monotonic()
        return (t1 - t0) * 1000

    try:
        import asyncio

        return asyncio.run(_measure())
    except RuntimeError:
        return 0.0


loop_latency_history: list[float] = []


def main() -> None:
    parser = argparse.ArgumentParser(description="Heartbeat para ura-mochila")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar en bucle cada 30s")
    args = parser.parse_args()

    fails = 0
    while not _shutdown_flag:
        if check_health():
            fails = 0
        else:
            fails += 1
            logger.error("Fallo %d/%d consecutivo", fails, MAX_FAILS)
            if fails >= MAX_FAILS:
                restart_service()
                fails = 0

        check_vram_pressure()

        global loop_latency_history  # noqa: PLW0602
        lat = check_loop_latency()
        if lat > 0:
            loop_latency_history.append(lat)
            if len(loop_latency_history) > 10:
                loop_latency_history.pop(0)
            avg_lat = sum(loop_latency_history) / len(loop_latency_history)
            if lat > 100.0 and avg_lat > 50.0:
                logger.warning("LOOP LATENCY: %.1fms (avg %.1fms)", lat, avg_lat)
                try:
                    from core.event_bus import publish

                    publish(
                        "alert",
                        {
                            "source": "heartbeat",
                            "function": "loop_monitor",
                            "loop_latency_ms": lat,
                            "loop_avg_ms": round(avg_lat, 1),
                        },
                    )
                except ImportError:
                    pass

        if not args.daemon:
            break
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    import signal

    def _handle_signal(sig, frame) -> None:
        global _shutdown_flag  # noqa: PLW0603
        logger.info("Recibida señal %s, parando heartbeat...", sig)
        _shutdown_flag = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    main()
