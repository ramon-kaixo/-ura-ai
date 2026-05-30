#!/usr/bin/env python3
"""
URA Node - Disk Check
Standalone disk monitoring node importing from core.disk_monitor.
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.disk_monitor import monitorear
from core.logging_config import get_logger
from nodes.node_utils import escribir_log, notificar_telegram

# Configuración
PORT = 8101
LOG_PATH = Path("logs/nodes/disk_check.jsonl")

logger = get_logger("disk_check_node", log_dir="./logs")


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler para /health endpoint."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""

    def do_GET(self):
        if self.path == "/health":
            resultado = monitorear()
            escribir_log(LOG_PATH, resultado)

            # Notificar por Telegram si estado == "error" o "warning"
            estado = resultado.get("estado")
            if estado in ("error", "warning"):
                mensaje = f"⚠️ Disk Alert: {resultado.get('gb_libres', 0):.2f} GB libres - Estado: {estado}"
                notificar_telegram(mensaje)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resultado).encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    """Main entry point - runs HTTP server."""
    logger.info(f"Iniciando Disk Check Node en puerto {PORT}")
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
