#!/usr/bin/env python3
"""
URA Nodes - Shared Utilities
Common functions for URA monitoring nodes.
"""

import json
from datetime import datetime, UTC
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger("nodes_utils", log_dir="./logs")


def notificar_telegram(mensaje: str):
    """Envía notificación por Telegram si el bridge está disponible."""
    try:
        from core.telegram_security_bridge import get_telegram_bridge

        bridge = get_telegram_bridge()
        bridge.send_message(mensaje)
    except Exception as e:
        logger.error(f"Error notificando por Telegram: {e}")


def escribir_log(path: Path, datos: dict):
    """Escribe datos a JSONL (append)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(datos, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Error escribiendo log en {path}: {e}")


def leer_ultimo_jsonl(path: Path):
    """Lee el último resultado de un JSONL específico."""
    try:
        if not path.exists():
            return {
                "estado": "pendiente",
                "mensaje": "sin ejecuciones previas",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()
                return json.loads(last_line)
            else:
                return {
                    "estado": "pendiente",
                    "mensaje": "sin ejecuciones previas",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
    except Exception as e:
        logger.error(f"Error leyendo {path}: {e}")
        return {"estado": "error", "error": str(e), "timestamp": datetime.now(UTC).isoformat()}
