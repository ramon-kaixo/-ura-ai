#!/usr/bin/env python3
"""
Telegram Notifier — Solo notificaciones, no procesa tareas.
Las tareas van por central_router.process_request().
"""

import sys
import logging
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("telegram_notifier")

# Leer token del .env
ENV_FILE = Path(__file__).parent / ".env"
TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == "TELEGRAM_TOKEN":
                TELEGRAM_TOKEN = v
            if k == "TELEGRAM_CHAT_ID":
                TELEGRAM_CHAT_ID = v


def send_message(text: str, chat_id: str = None) -> bool:
    """Enviar mensaje por Telegram."""
    if not TELEGRAM_TOKEN:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id or TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Error enviando Telegram: {e}")
        return False


def notify_task_complete(task: str, result: str, duration: float = 0):
    """Notificar tarea completada."""
    msg = f"✅ *Tarea completada*\n📋 {task[:100]}\n⏱️ {duration:.0f}s\n📄 {result[:200]}"
    send_message(msg)


def notify_alert(alert_type: str, message: str):
    """Notificar alerta crítica."""
    msg = f"🚨 *{alert_type}*\n{message[:300]}"
    send_message(msg)


if __name__ == "__main__":
    if TELEGRAM_TOKEN:
        send_message("🟢 URA Telegram Notifier activo")
        logger.info("Notificación de prueba enviada")
    else:
        logger.warning("TELEGRAM_TOKEN no configurado")
