#!/usr/bin/env python3
"""
URA Node - RAM Check
Standalone RAM monitoring node using psutil.
"""

import json
import sys
from datetime import datetime, UTC
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psutil

from core.logging_config import get_logger
from nodes.node_utils import escribir_log, leer_ultimo_jsonl, notificar_telegram

# Configuración
PORT = 8106
LOG_PATH = Path("logs/nodes/ram_check.jsonl")

logger = get_logger("ram_check_node", log_dir="./logs")


def ejecutar_check():
    """Ejecuta check de RAM y escribe resultado a JSONL."""
    try:
        # Obtener información de memoria
        mem = psutil.virtual_memory()

        ram_total_gb = mem.total / (1024**3)
        ram_libre_gb = mem.available / (1024**3)
        porcentaje_uso = mem.percent

        # Determinar estado
        estado = "warning" if ram_libre_gb < 2 else "ok"

        resultado = {
            "estado": estado,
            "ram_libre_gb": round(ram_libre_gb, 2),
            "ram_total_gb": round(ram_total_gb, 2),
            "porcentaje_uso": round(porcentaje_uso, 2),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(
            f"RAM check: {ram_libre_gb:.2f} GB libres / {ram_total_gb:.2f} GB total ({porcentaje_uso:.1f}% uso)"
        )

        # Escribir a JSONL
        escribir_log(LOG_PATH, resultado)

        # Notificar por Telegram si ram_libre_gb < 2
        if ram_libre_gb < 2:
            mensaje = (
                f"⚠️ RAM Check: Solo {ram_libre_gb:.2f} GB libres ({porcentaje_uso:.1f}% usado)"
            )
            notificar_telegram(mensaje)

        return resultado

    except Exception as e:
        logger.error(f"Error en RAM check: {e}")
        return {
            "estado": "error",
            "ram_libre_gb": 0,
            "ram_total_gb": 0,
            "porcentaje_uso": 0,
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }


def leer_ultimo_resultado():
    """Lee el último resultado del JSONL sin ejecutar check."""
    return leer_ultimo_jsonl(LOG_PATH)


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler para /health endpoint."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""

    def do_GET(self):
        if self.path == "/health":
            resultado = leer_ultimo_resultado()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resultado).encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    """Main entry point - runs HTTP server."""
    logger.info(f"Iniciando RAM Check Node en puerto {PORT}")
    logger.info(f"Logs en: {LOG_PATH}")

    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)  # nosec: B104
    logger.info(f"Servidor HTTP listo en http://0.0.0.0:{PORT}/health")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Deteniendo servidor...")
        server.shutdown()


if __name__ == "__main__":
    main()
