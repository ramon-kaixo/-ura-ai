#!/usr/bin/env python3
"""
URA Node - Ollama Health Check
Standalone Ollama health monitoring node with simple requests-based check.
"""

import json
import logging
import sys
import time
from datetime import datetime, UTC
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from nodes.node_utils import escribir_log, notificar_telegram

# Configuración
PORT = 8102
OLLAMA_URL = "http://localhost:11434/api/tags"
LOG_PATH = Path("logs/nodes/ollama_health.jsonl")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ollama_health_node")


def check_ollama():
    """Verifica salud de Ollama con requests.get simple (copia de test_connection línea 180)."""
    try:
        start_time = time.time()
        response = requests.get(OLLAMA_URL, timeout=30)
        latencia_ms = round((time.time() - start_time) * 1000, 2)
        timestamp = datetime.now(tz=UTC).isoformat()

        if response.status_code == 200:
            resultado = {
                "estado": "ok",
                "latencia_ms": latencia_ms,
                "timestamp": timestamp,
            }
            logger.info(f"Ollama OK: {latencia_ms}ms")
        else:
            resultado = {
                "estado": "caido",
                "latencia_ms": latencia_ms,
                "timestamp": timestamp,
            }
            logger.warning(f"Ollama responde con status {response.status_code}")

        return resultado

    except Exception as e:
        logger.error(f"Error en conexión con Ollama: {e}")
        return {
            "estado": "caido",
            "latencia_ms": 0,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler para /health endpoint."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""

    def do_GET(self):
        if self.path == "/health":
            resultado = check_ollama()
            escribir_log(LOG_PATH, resultado)

            # Notificar por Telegram si estado == "caido"
            if resultado.get("estado") == "caido":
                mensaje = f"⚠️ Ollama Alert: Servicio no responde - Latencia: {resultado.get('latencia_ms')}ms"
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
    logger.info(f"Iniciando Ollama Health Node en puerto {PORT}")
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
