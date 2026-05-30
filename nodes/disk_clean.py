#!/usr/bin/env python3
"""
URA Node - Disk Cleaner
Standalone disk cleaning node importing from core.disk_cleaner.
"""

import json
import sys
from datetime import datetime, UTC
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.disk_cleaner import limpiar
from core.logging_config import get_logger
from nodes.node_utils import escribir_log, leer_ultimo_jsonl, notificar_telegram

# Configuración
PORT = 8103
LOG_PATH = Path("logs/nodes/disk_clean.jsonl")

logger = get_logger("disk_clean_node", log_dir="./logs")


def ejecutar_limpieza():
    """Ejecuta limpieza de disco y escribe resultado a JSONL."""
    try:
        # Ejecutar limpieza en modo safe
        resultado = limpiar(modo="safe")

        # Formatear resultado para el nodo
        resultado_formateado = {
            "estado": "ok" if resultado["ok"] else "error",
            "espacio_liberado_mb": resultado["espacio_liberado_mb"],
            "acciones": resultado["acciones"],
            "errores": resultado["errores"],
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(f"Disk cleaner: {resultado_formateado['espacio_liberado_mb']:.2f} MB liberados")

        # Escribir a JSONL
        escribir_log(LOG_PATH, resultado_formateado)

        # Notificar por Telegram si se liberó espacio
        if resultado["ok"] and resultado["espacio_liberado_mb"] > 0:
            mensaje = f"🧹 Disk Cleaner: {resultado['espacio_liberado_mb']:.2f} MB liberados"
            notificar_telegram(mensaje)

        return resultado_formateado

    except Exception as e:
        logger.error(f"Error en disk cleaner: {e}")
        return {
            "estado": "error",
            "espacio_liberado_mb": 0,
            "acciones": [],
            "errores": [str(e)],
            "timestamp": datetime.now(UTC).isoformat(),
        }


def leer_ultimo_resultado():
    """Lee el último resultado del JSONL sin ejecutar limpieza."""
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

    def do_POST(self):
        if self.path == "/ejecutar":
            resultado = ejecutar_limpieza()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resultado).encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    """Main entry point - runs HTTP server."""
    logger.info(f"Iniciando Disk Clean Node en puerto {PORT}")
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
