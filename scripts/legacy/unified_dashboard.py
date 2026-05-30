#!/usr/bin/env python3
"""
Panel de Control Unificado - URA App
Dashboard + Conversaciones + Herramientas en una sola interfaz
"""

import os
from datetime import datetime
from pathlib import Path

import psutil
import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)


class UnifiedDashboard:
    """Panel de control unificado"""

    def __init__(self):
        self.ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")

    def obtener_estado_sistema(self) -> Dict:
        """Obtener estado completo del sistema"""
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {"percent": psutil.cpu_percent(interval=1), "count": psutil.cpu_count()},
            "ram": {
                "percent": psutil.virtual_memory().percent,
                "available_gb": psutil.virtual_memory().available / (1024**3),
            },
            "disco": {
                "percent": psutil.disk_usage("/").percent,
                "free_gb": psutil.disk_usage("/").free / (1024**3),
            },
            "ollama": self._verificar_ollama(),
            "redis": self._verificar_redis(),
            "docker": self._verificar_docker(),
        }

    def _verificar_ollama(self) -> Dict:
        """Verificar Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            return {"status": "ok", "modelos": len(response.json().get("models", []))}
        except:
            return {"status": "error"}

    def _verificar_redis(self) -> Dict:
        """Verificar Redis"""
        try:
            import redis

            r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
            r.ping()
            return {"status": "ok"}
        except:
            return {"status": "error"}

    def _verificar_docker(self) -> Dict:
        """Verificar Docker"""
        try:
            import subprocess

            result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
            return {"status": "ok" if "ura-sandbox" in result.stdout else "error"}
        except:
            return {"status": "error"}

    def obtener_conversaciones(self) -> Dict:
        """Obtener conversaciones"""
        from scripts.conversation_to_ura import conversation_to_ura

        return {
            "pendientes": conversation_to_ura.obtener_conversaciones_pendientes(),
            "total": len(conversation_to_ura.obtener_conversaciones_pendientes()),
        }

    def obtener_herramientas(self) -> Dict:
        """Obtener estado de herramientas"""
        from core.tool_manager import tool_manager

        return {
            "herramientas": tool_manager.listar_herramientas(),
            "total": len(tool_manager.listar_herramientas()),
        }


dashboard = UnifiedDashboard()


@app.route("/")
def index():
    """Página principal del dashboard unificado"""
    return render_template("unified_dashboard.html")


@app.route("/api/estado")
def api_estado():
    """API endpoint para estado del sistema"""
    return jsonify(dashboard.obtener_estado_sistema())


@app.route("/api/conversaciones")
def api_conversaciones():
    """API endpoint para conversaciones"""
    return jsonify(dashboard.obtener_conversaciones())


@app.route("/api/herramientas")
def api_herramientas():
    """API endpoint para herramientas"""
    return jsonify(dashboard.obtener_herramientas())


@app.route("/api/alertas")
def api_alertas():
    """API endpoint para alertas"""
    from core.proactive_alerts import proactive_alerts

    return jsonify(proactive_alerts.verificar_todo())


if __name__ == "__main__":
    print("Dashboard unificado iniciado en http://localhost:5002")
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=5002,
    )
