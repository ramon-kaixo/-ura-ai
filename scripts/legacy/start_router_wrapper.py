#!/usr/bin/env python3
"""Script wrapper para central_router - arranca con auto-recovery."""

import subprocess
import time
import sys
import os
import logging
from pathlib import Path

logging.basicConfig(
    filename=str(Path.home() / "URA" / "ura_ia_1972" / "logs" / "router_wrapper.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

ROUTER_SCRIPT = Path.home() / "URA" / "ura_ia_1972" / "services" / "llama_router.py"


def is_router_running():
    """Verificar si llama_router.py ya está corriendo."""
    result = subprocess.run(["pgrep", "-f", "llama_router.py"], capture_output=True, text=True)
    return result.returncode == 0


def start_router():
    """Iniciar llama_router.py como proceso hijo."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.home() / "URA" / "ura_ia_1972") + ":" + env.get("PYTHONPATH", "")
    env["OLLAMA_MAX_LOADED_MODELS"] = "4"

    log_file = Path.home() / "URA" / "ura_ia_1972" / "logs" / "llama_router.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [
            sys.executable,
            str(ROUTER_SCRIPT),
            "--host",
            "100.127.206.86",
            "--models",
            "codestral-22b",
            "qwen2.5-coder-q8",
            "qwen2.5-coder-32b",
        ],
        stdout=open(str(log_file), "a"),
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    logging.info(f"Router iniciado PID={proc.pid}")
    return proc


if __name__ == "__main__":
    os.chdir(Path.home() / "URA" / "ura_ia_1972")

    if is_router_running():
        logging.info("Router ya está corriendo, no hace nada")
        sys.exit(0)

    logging.info("Router no detectado, iniciando...")
    start_router()
    time.sleep(5)

    if is_router_running():
        logging.info("Router iniciado exitosamente")
    else:
        logging.error("Router falló al iniciar")
