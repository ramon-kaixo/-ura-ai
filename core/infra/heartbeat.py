#!/usr/bin/env python3
"""Heartbeat check para ura-mochila.service.
Reinicia el servicio si /health falla 3 veces consecutivas.

Uso:
  python3 core/infra/heartbeat.py                  # una ejecucion
  python3 core/infra/heartbeat.py --daemon         # bucle cada 30s
"""
import argparse
import logging
import subprocess
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ura.heartbeat")

MOCHILA_URL = "http://127.0.0.1:4098"
HEALTH_PATH = "/health"
MAX_FAILS = 3
CHECK_INTERVAL = 30


def check_health() -> bool:
    try:
        req = Request(f"{MOCHILA_URL}{HEALTH_PATH}", method="GET")
        with urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (URLError, OSError, ValueError) as e:
        logger.warning("Health check fallo: %s", e)
        return False


def restart_service():
    logger.critical("Reiniciando ura-mochila.service...")
    try:
        res = subprocess.run(
            ["systemctl", "restart", "ura-mochila.service"],
            capture_output=True, text=True, timeout=30,
        )
        if res.returncode == 0:
            logger.info("ura-mochila.service reiniciado exitosamente")
        else:
            logger.error("Fallo restart: %s", res.stderr.strip())
    except subprocess.TimeoutExpired:
        logger.error("Timeout al reiniciar servicio")
    except FileNotFoundError:
        logger.error("systemctl no disponible")


def main():
    parser = argparse.ArgumentParser(description="Heartbeat para ura-mochila")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar en bucle cada 30s")
    args = parser.parse_args()

    fails = 0
    while True:
        if check_health():
            fails = 0
        else:
            fails += 1
            logger.error("Fallo %d/%d consecutivo", fails, MAX_FAILS)
            if fails >= MAX_FAILS:
                restart_service()
                fails = 0

        if not args.daemon:
            break
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
