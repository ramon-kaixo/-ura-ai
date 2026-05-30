#!/usr/bin/env python3
"""
Health Monitor Triángulo URA.
Monitorea Mac ↔ GX10 ↔ Hetzner cada 5 minutos.
Alerta vía log y opcionalmente Telegram.
"""

import json
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path

import requests

ALERT_LOG = Path.home() / ".ura" / "tria_health.log"
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)

NODES = {
    "GX10": "10.164.1.99",
    "Hetzner": "100.90.84.4",
}
OLLAMA_URL = "http://10.164.1.99:11434/api/tags"
CHECK_INTERVAL = 300  # 5 minutos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(ALERT_LOG),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("tria_health")


def ping(host: str, timeout: int = 3) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout * 1000), host],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_ollama() -> tuple[bool, list[str]]:
    try:
        r = requests.get(OLLAMA_URL, timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, models
    except Exception as e:
        logger.debug(f"Ollama check failed: {e}")
    return False, []


def check_exit_node() -> tuple[bool, str]:
    try:
        r = requests.get("https://ifconfig.me", timeout=5)
        ip = r.text.strip()
        # IP esperada del exit node Hetzner
        return ip == "178.105.81.83", ip
    except Exception:
        return False, "unreachable"


def run_check() -> dict:
    status = {"timestamp": datetime.now().isoformat(), "checks": {}}

    for name, ip in NODES.items():
        ok = ping(ip)
        status["checks"][f"ping_{name}"] = {"ok": ok, "ip": ip}
        if not ok:
            logger.warning(f"❌ Ping {name} ({ip}) FAILED")
        else:
            logger.info(f"✅ Ping {name} ({ip}) OK")

    ollama_ok, models = check_ollama()
    status["checks"]["ollama"] = {"ok": ollama_ok, "models": models}
    if ollama_ok:
        logger.info(f"✅ Ollama OK ({len(models)} modelos)")
    else:
        logger.warning("❌ Ollama API NO responde")

    exit_ok, ip = check_exit_node()
    status["checks"]["exit_node"] = {"ok": exit_ok, "public_ip": ip}
    if exit_ok:
        logger.info(f"✅ Exit Node Hetzner OK ({ip})")
    else:
        logger.warning(f"⚠️  IP pública {ip} NO es Hetzner (exit node inactivo?)")

    return status


def main():
    logger.info("=== Health Monitor Triángulo iniciado ===")
    while True:
        try:
            status = run_check()
            # JSON para parsing
            with open(ALERT_LOG.parent / "tria_health.json", "w") as f:
                json.dump(status, f, indent=2)
        except KeyboardInterrupt:
            logger.info("Detenido manualmente")
            break
        except Exception as e:
            logger.error(f"Error en check: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
