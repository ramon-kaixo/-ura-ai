#!/usr/bin/env python3
"""
Dashboard de Monitorización en Tiempo Real - URA App
Muestra estado del sistema en tiempo real vía web
"""

import os
import time
from datetime import datetime

import psutil
import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)


def obtener_estado_sistema():
    """Obtener estado completo del sistema"""
    estado = {
        "timestamp": datetime.now().isoformat(),
        "cpu": obtener_cpu(),
        "ram": obtener_ram(),
        "disco": obtener_disco(),
        "ollama": obtener_ollama(),
        "redis": obtener_redis(),
        "docker": obtener_docker(),
    }
    return estado


def obtener_cpu():
    """Obtener estado de CPU"""
    return {
        "percent": psutil.cpu_percent(interval=1),
        "count": psutil.cpu_count(),
        "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
    }


def obtener_ram():
    """Obtener estado de RAM"""
    ram = psutil.virtual_memory()
    return {
        "total_gb": ram.total / (1024**3),
        "available_gb": ram.available / (1024**3),
        "percent": ram.percent,
        "used_gb": ram.used / (1024**3),
    }


def obtener_disco():
    """Obtener estado de disco"""
    disco = psutil.disk_usage("/")
    return {
        "total_gb": disco.total / (1024**3),
        "free_gb": disco.free / (1024**3),
        "used_gb": disco.used / (1024**3),
        "percent": disco.percent,
    }


def obtener_ollama():
    """Obtener estado de Ollama"""
    try:
        inicio = time.time()
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        latencia = time.time() - inicio

        return {
            "status": "ok" if response.status_code == 200 else "error",
            "latencia_s": latencia,
            "modelos": len(response.json().get("models", [])) if response.status_code == 200 else 0,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def obtener_redis():
    """Obtener estado de Redis"""
    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
        inicio = time.time()
        r.ping()
        latencia = time.time() - inicio

        return {"status": "ok", "latencia_s": latencia}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def obtener_docker():
    """Obtener estado de Docker"""
    try:
        import subprocess

        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10
        )

        contenedores = result.stdout.strip().split("\n") if result.stdout.strip() else []

        return {
            "status": "ok" if result.returncode == 0 else "error",
            "contenedores": contenedores,
            "ura_sandbox_activo": "ura-sandbox" in contenedores,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.route("/")
def index():
    """Página principal del dashboard"""
    return render_template("dashboard.html")


@app.route("/api/estado")
def api_estado():
    """API endpoint para estado del sistema"""
    return jsonify(obtener_estado_sistema())


@app.route("/api/alertas")
def api_alertas():
    """API endpoint para alertas"""
    from core.proactive_alerts import proactive_alerts

    alertas = proactive_alerts.verificar_todo()
    return jsonify(alertas)


if __name__ == "__main__":
    print("Dashboard de monitorización iniciado en http://localhost:5000")
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=5000,
    )
