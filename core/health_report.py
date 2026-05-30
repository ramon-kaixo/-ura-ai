#!/usr/bin/env python3
"""
URA Node - Health Report
Aggregator node that reads all node JSONL logs and creates a summary.
"""

import json
import sys
from datetime import datetime, UTC
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logging_config import get_logger
from nodes.node_utils import escribir_log, leer_ultimo_jsonl, notificar_telegram

# Configuración
PORT = 8108
LOG_PATH = Path("logs/nodes/health_report.jsonl")

# Rutas de los JSONL de todos los nodos
NODE_LOGS = {
    "disk_check": Path("logs/nodes/disk_check.jsonl"),
    "ollama_health": Path("logs/nodes/ollama_health.jsonl"),
    "disk_clean": Path("logs/nodes/disk_clean.jsonl"),
    "thread_cleaner": Path("logs/nodes/thread_cleaner.jsonl"),
    "network_audit": Path("logs/nodes/network_audit.jsonl"),
    "ram_check": Path("logs/nodes/ram_check.jsonl"),
    "cloud_backup": Path("logs/nodes/cloud_backup.jsonl"),
}

logger = get_logger("health_report_node", log_dir="./logs")


def ejecutar_reporte():
    """Lee todos los JSONL de nodos y crea resumen."""
    try:
        resumen = {}
        nodos_con_error = []

        # Leer todos los nodos
        for nombre, ruta in NODE_LOGS.items():
            resultado = leer_ultimo_jsonl(ruta)
            resumen[nombre] = resultado

            # Verificar si hay error
            estado = resultado.get("estado", "unknown")
            if estado not in ("ok", "pendiente"):
                nodos_con_error.append(nombre)

        # Determinar estado general
        if nodos_con_error:
            estado_general = "error"
        elif any(v.get("estado") == "pendiente" for v in resumen.values()):
            estado_general = "warning"
        else:
            estado_general = "ok"

        resultado = {
            "estado": estado_general,
            "resumen": resumen,
            "nodos_con_error": nodos_con_error,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(f"Health report: {estado_general} - {len(nodos_con_error)} nodos con error")

        # Escribir a JSONL
        escribir_log(LOG_PATH, resultado)

        # Notificar por Telegram si hay nodos con error
        if nodos_con_error:
            mensaje = f"⚠️ Health Report: Nodos con error - {nodos_con_error}"
            notificar_telegram(mensaje)

        return resultado

    except Exception as e:
        logger.error(f"Error en health report: {e}")
        return {
            "estado": "error",
            "resumen": {},
            "nodos_con_error": [],
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }


def leer_ultimo_resultado():
    """Lee el último resultado del JSONL sin ejecutar reporte."""
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
    logger.info(f"Iniciando Health Report Node en puerto {PORT}")
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
