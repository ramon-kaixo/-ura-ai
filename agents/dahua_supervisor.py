#!/usr/bin/env python3
"""dahua_supervisor.py — Supervisa camaras Dahua via HTTP API sin Docker
Consulta el estado de cada camara y publica eventos via MQTT.
No modifica la configuracion de las camaras, solo lee."""

import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

CONFIG = Path(os.environ.get("DAHUA_CONFIG", str(Path.home() / "URA/dahua_config/cameras.json")))
LOG = Path(os.environ.get("DAHUA_LOG", str(Path.home() / "URA/logs/dahua_supervisor.log")))
INTERVALO = int(os.environ.get("DAHUA_INTERVALO", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG), logging.StreamHandler()],
)


def check_camera(host: str, user: str, password: str, name: str) -> dict:
    """Consulta el estado de una camara Dahua via HTTP API."""
    result = {"name": name, "host": host, "online": False, "error": None}
    url = f"http://{host}/cgi-bin/status.cgi"
    try:
        req = Request(url)
        req.add_header(
            "Authorization",
            f"Basic {__import__('base64').b64encode(f'{user}:{password}'.encode()).decode()}",
        )
        with urlopen(req, timeout=5) as resp:
            data = resp.read().decode()
            result["online"] = True
            result["respuesta"] = data[:200]
    except URLError as e:
        result["error"] = str(e.reason)
    except Exception as e:
        result["error"] = str(e)
    return result


def publicar_mqtt(topic: str, mensaje: str):
    """Publica un mensaje MQTT (si mosquitto esta disponible)."""
    subprocess.run(
        ["mosquitto_pub", "-h", "localhost", "-t", topic, "-m", mensaje],
        capture_output=True,
        timeout=5,
    )


def main():
    if not CONFIG.exists():
        logging.error(f"Config no encontrada: {CONFIG}")
        return

    with open(CONFIG) as f:
        cfg = json.load(f)

    logging.info(f"Supervisor Dahua iniciado — {len(cfg['cameras'])} camaras")
    offline_count = 0

    for cam in cfg["cameras"]:
        status = check_camera(
            cam["host"], cam.get("username", "admin"), cam.get("password", "admin"), cam["name"]
        )
        if status["online"]:
            logging.info(f"  OK  {cam['name']} ({cam['host']})")
        else:
            offline_count += 1
            logging.warning(f"  OFF {cam['name']} ({cam['host']}): {status['error']}")
            topic = f"{cfg.get('mqtt', {}).get('topic_prefix', 'ura/camaras')}/{cam['name']}/status"
            publicar_mqtt(
                topic,
                json.dumps(
                    {"online": False, "error": status["error"], "time": datetime.now().isoformat()}
                ),
            )

    logging.info(f"Resumen: {len(cfg['cameras']) - offline_count}/{len(cfg['cameras'])} online")
    return offline_count == 0


if __name__ == "__main__":
    main()
