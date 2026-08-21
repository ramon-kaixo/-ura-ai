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
from motor.core.secrets import get_secret

STATE_FILE = "/tmp/ura_state.json"

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
        token = get_secret("URA_API_KEY") or ""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        req = Request(  # noqa: S310
            f"{MOCHILA_URL}{HEALTH_PATH}",
            method="GET",
            headers=headers,
        )
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
        from motor.core.qdrant_client import QdrantClient

        cfg = UraConfig()
        qc = QdrantClient.instancia(cfg)
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
            ["systemctl", "restart", "ura-mochila.service"],
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
# P11 (2026-08-18): umbral subido de 22000 a 64000 MB. La carga normal con el
# modelo de refactor (qwen2.5-coder:32b en ollama, 50.9GB segun nvidia-smi) +
# llama-server (6.7GB) superaba 22GB -> falsos vram_panic_restart continuos
# (restart de mochila fallido por auth, ruido operativo). 64GB cubre la carga
# observada (~59GB) con margen y mantiene el pánico para saturacion real
# (2+ modelos grandes simultaneos).
VRAM_PANIC_MB = 64000


def _vram_used_mb() -> int:
    """Consultar VRAM usada por los procesos compute (MiB)."""
    cmd = [
        "nvidia-smi",
        "--query-compute-apps=used_memory",
        "--format=csv,noheader,nounits",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
    total_used = 0
    for line in res.stdout.strip().split("\n"):
        line = line.strip()  # noqa: PLW2901
        if line.isdigit():
            total_used += int(line)
    return total_used


def _reportar_vram(
    evento: str, result_type: str, reason: str = "", sandbox_errors: list[str] | None = None, attempts: int = 0
) -> None:
    """Registrar evento de monitorización VRAM en el log del guardián."""
    log_event(
        evento,
        model="",
        file="",
        reason=reason,
        attempts=attempts,
        penalty="",
        sandbox_errors=sandbox_errors or [],
        complexity=0,
        temperature=0.0,
        result_type=result_type,
    )


def check_vram_pressure() -> None:
    global vram_critical_cycles  # noqa: PLW0603
    try:
        total_used = _vram_used_mb()

        if total_used > VRAM_PANIC_MB:
            vram_critical_cycles += 1
            _reportar_vram("vram_pressure_high", "warning", attempts=vram_critical_cycles)
            logger.warning("VRAM pressure: %d MB used (%d/%d cycles)", total_used, vram_critical_cycles, 3)
            if vram_critical_cycles >= 3:
                _reportar_vram(
                    "vram_panic_restart",
                    "failure",
                    sandbox_errors=[f"VRAM saturation {total_used} MB > {VRAM_PANIC_MB} MB"],
                    attempts=3,
                )
                logger.critical("VRAM panic: restarting mochila")
                restart_service()
                vram_critical_cycles = 0
        else:
            vram_critical_cycles = 0
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        _reportar_vram("vram_monitor_error", "failure", reason=str(e))
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
                except ImportError as exc:
                    logger.debug("modulo opcional no disponible: %s", exc)
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
