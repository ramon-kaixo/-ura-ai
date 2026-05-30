#!/usr/bin/env python3
"""
agente_reparador.py — Reparador automático de errores del sistema
"""

import logging

logger = logging.getLogger(__name__)
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

SISTEMA = Path(__file__).parent.parent
LOG = SISTEMA / "logs" / "reparador.log"
LOG.parent.mkdir(exist_ok=True)

ERRORES_CONOCIDOS = {
    "port.*already.*use": {
        "solucion": "lsof -ti:PUERTO | xargs kill -9",
        "descripcion": "Puerto ocupado por otro proceso",
    },
    "ollama.*not.*running": {
        "solucion": "brew services start ollama",
        "descripcion": "Ollama no está corriendo",
    },
    "connection.*refused": {
        "solucion": "Reiniciar servicio correspondiente",
        "descripcion": "Conexión rechazada",
    },
    "permission.*denied": {
        "solucion": "sudo chown -R usuario:staff RUTA",
        "descripcion": "Permisos insuficientes",
    },
    "no.*space.*left": {"solucion": "df -h y limpiar disco", "descripcion": "Disco lleno"},
    "module.*not.*found": {
        "solucion": "pip install MODULO",
        "descripcion": "Módulo Python faltante",
    },
    "database.*locked": {
        "solucion": "Cerrar conexiones y reintentar",
        "descripcion": "Base de datos bloqueada",
    },
    "docker.*not.*running": {
        "solucion": "open -a Docker",
        "descripcion": "Docker no está corriendo",
    },
    "address.*already.*in.*use": {
        "solucion": "lsof -ti:PUERTO | xargs kill -9",
        "descripcion": "Dirección ya en uso",
    },
}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def detectar_tipo_error(error_msg):
    error_lower = error_msg.lower()
    for patron, info in ERRORES_CONOCIDOS.items():
        if re.search(patron, error_lower):
            return info
    return None


def obtener_servicios():
    servicios = []
    try:
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
        for linea in result.stdout.split("\n")[1:]:
            partes = linea.split()
            if len(partes) >= 3:
                servicios.append(partes[2])
    except Exception as e:
        logger.warning(f"Error silencioso en agente_reparador.get_services: {e}")
        # fallback: lista vacía
    return servicios


def verificar_ollama():
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"], capture_output=True, timeout=3
        )
        return result.returncode == 0
    except:
        return False


def verificar_docker():
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def verificar_panel():
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:5051"],
            capture_output=True,
            timeout=3,
        )
        return "200" in result.stdout.decode()
    except:
        return False


def obtener_estado_servicios():
    return {"ollama": verificar_ollama(), "docker": verificar_docker(), "panel": verificar_panel()}


def intentar_reparacion(error_msg):
    info_error = detectar_tipo_error(error_msg)

    if not info_error:
        log(f"ERROR DESCONOCIDO: {error_msg}")
        return {"reparado": False, "mensaje": "Error desconocido, requiere intervención manual"}

    log(f"ERROR DETECTADO: {info_error['descripcion']}")
    log(f"SOLUCION: {info_error['solucion']}")

    servicios = obtener_estado_servicios()

    if not servicios["ollama"]:
        try:
            subprocess.run(["brew", "services", "start", "ollama"], timeout=30)
            log("Ollama iniciado")
        except Exception as e:
            log(f"Error iniciando Ollama: {e}")

    if not servicios["docker"]:
        try:
            subprocess.run(["open", "-a", "Docker"], timeout=10)
            log("Docker iniciado")
        except Exception as e:
            log(f"Error iniciando Docker: {e}")

    return {"reparado": True, "mensaje": f"Reparación intentada: {info_error['descripcion']}"}


def generar_informe():
    servicios = obtener_estado_servicios()

    informe = f"""
╔══════════════════════════════════════════════════════╗
║       INFORME DEL REPARADOR — {datetime.now().strftime("%Y-%m-%d %H:%M")}
╠══════════════════════════════════════════════════════╣
║  Ollama:    {"✅ Activo" if servicios["ollama"] else "❌ Inactivo"}
║  Docker:    {"✅ Activo" if servicios["docker"] else "❌ Inactivo"}
║  Panel:     {"✅ Activo" if servicios["panel"] else "❌ Inactivo"}
╚══════════════════════════════════════════════════════╝
"""
    return informe


if __name__ == "__main__":
    import sys

    if "--reparar" in sys.argv and len(sys.argv) > 2:
        resultado = intentar_reparacion(" ".join(sys.argv[2:]))
        print(resultado["mensaje"])
    elif "--informe" in sys.argv:
        print(generar_informe())
    elif "--estado" in sys.argv:
        import json

        print(json.dumps(obtener_estado_servicios()))
    else:
        print(generar_informe())
