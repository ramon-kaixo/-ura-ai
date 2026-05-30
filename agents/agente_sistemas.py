#!/usr/bin/env python3
"""
AGENTE SISTEMAS - Monitorización y administración del sistema local
 Integrado con Registry: 15 agentes consolidados
"""

import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Imports del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.observability import URALogger

logger = URALogger("agente_sistemas")

# ============================================================
# CONFIGURACIÓN - Redes locales de Ramón
# ============================================================
DISPOSITIVOS = {
    "router": {"host": "192.168.1.1", "tipo": "router", "critico": True},
    "camara_patio": {"host": "192.168.1.110", "tipo": "camera", "critico": True, "puerto": 80},
    "camara_entrada": {"host": "192.168.1.111", "tipo": "camera", "critico": True, "puerto": 80},
    "camara_garaje": {"host": "192.168.1.112", "tipo": "camera", "critico": False, "puerto": 80},
    "nas": {"host": "192.168.1.200", "tipo": "nas", "critico": True, "puerto": 5000},
    "imac": {"host": "192.168.1.50", "tipo": "computer", "critico": False},
}

# Telegram - Usar variable de entorno
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
if not TOKEN:
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8621907530")
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""


# ============================================================
# HERRAMIENTAS DEL AGENTE
# ============================================================
def ping(host: str, timeout: int = 3) -> bool:
    """Ping a un host"""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-t", str(timeout), host], capture_output=True, timeout=timeout + 1
        )
        return result.returncode == 0
    except:
        return False


def check_http(host: str, puerto: int = 80, path: str = "/") -> dict:
    """Check HTTP de un dispositivo"""
    try:
        url = f"http://{host}:{puerto}{path}"
        response = requests.get(url, timeout=5)
        return {
            "status": response.status_code,
            "ok": response.status_code == 200,
            "latencia_ms": int(response.elapsed.total_seconds() * 1000),
        }
    except requests.exceptions.Timeout:
        return {"status": 0, "ok": False, "error": "timeout"}
    except Exception as e:
        return {"status": 0, "ok": False, "error": str(e)}


def check_puerto(host: str, puerto: int) -> bool:
    """Check si un puerto está abierto"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        result = sock.connect_ex((host, puerto))
        return result == 0
    except:
        return False
    finally:
        sock.close()


def notificar_telegram(mensaje: str, urgente: bool = False):
    """Enviar notificación directa"""
    try:
        prefix = "🚨 " if urgente else "📡 "
        requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            data={"chat_id": CHAT_ID, "text": prefix + mensaje},
            timeout=10,
        )
    except Exception as e:
        print(f"Error notificando: {e}")


# ============================================================
# SENSORES DEL AGENTE
# ============================================================
def sensor_red() -> dict:
    """Monitorear red local"""
    resultados = {}

    for nombre, config in DISPOSITIVOS.items():
        host = config["host"]

        # 1. Ping básico
        ping_ok = ping(host)

        # 2. Si es HTTP, check específico
        http_result = None
        if "puerto" in config:
            http_result = check_http(host, config.get("puerto", 80))

        # Determinar estado
        estado = "OK" if ping_ok else "OFFLINE"
        if http_result and not http_result.get("ok"):
            estado = "ERROR"

        resultados[nombre] = {
            "host": host,
            "ping": ping_ok,
            "http": http_result,
            "estado": estado,
            "critico": config.get("critico", False),
            "timestamp": datetime.now().isoformat(),
        }

        # ALERTA SI CRÍTICO Y FALLA
        if config.get("critico", False) and not ping_ok:
            notificar_telegram(
                f"⚠️ {nombre.upper()} OFFLINE\nHost: {host}\nTipo: {config['tipo']}", urgente=True
            )

    return resultados


def sensor_recursos() -> dict:
    """Monitorear recursos del Mac"""
    import psutil

    cpu = psutil.cpu_percent(interval=1)
    memoria = psutil.virtual_memory().percent
    disco = psutil.disk_usage("/").percent

    # Alertas
    if cpu > 90:
        notificar_telegram(f"⚠️ CPU ALTO: {cpu}%", urgente=True)
    if memoria > 90:
        notificar_telegram(f"⚠️ MEMORIA ALTA: {memoria}%", urgente=True)
    if disco > 95:
        notificar_telegram(f"🚨 DISCO LLENO: {disco}%", urgente=True)

    return {"cpu": cpu, "memoria": memoria, "disco": disco, "timestamp": datetime.now().isoformat()}


def sensor_servicios() -> dict:
    """Monitorear servicios URA"""
    servicios = {"telegram": "telegram_run.py", "ollama": "ollama serve", "board": "board.db"}

    resultados = {}
    for nombre, proceso in servicios.items():
        resultado = subprocess.run(["pgrep", "-f", proceso], capture_output=True)
        corriendo = resultado.returncode == 0
        resultados[nombre] = {"activo": corriendo, "proceso": proceso}

        # Alertar si servicio crítico cae
        if nombre in ["telegram", "ollama"] and not corriendo:
            notificar_telegram(f"🚨 SERVICIO CAÍDO: {nombre}", urgente=True)

    return resultados


# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================
def ejecutar(comando: str) -> str:
    """Ejecutar comando en lenguaje natural"""
    logger.log_inicio({"comando": comando})

    comando = comando.lower()

    # Comandos disponibles
    if "red" in comando or "camaras" in comando or "cámaras" in comando:
        resultados = sensor_red()

        output = "📡 ESTADO RED LOCAL\n"
        output += "=" * 30 + "\n"

        for nombre, datos in resultados.items():
            icon = "✅" if datos["estado"] == "OK" else "❌"
            critico = " 🔴" if datos.get("critico") else ""
            output += f"{icon} {nombre:15} {datos['host']:15} {datos['estado']}{critico}\n"

        logger.log_ok(output)
        return output

    elif "recursos" in comando or "cpu" in comando or "memoria" in comando:
        recursos = sensor_recursos()

        output = "💻 RECURSOS SISTEMA\n"
        output += "=" * 30 + "\n"
        output += f"CPU:     {recursos['cpu']}%\n"
        output += f"Memoria: {recursos['memoria']}%\n"
        output += f"Disco:   {recursos['disco']}%\n"

        logger.log_ok(output)
        return output

    elif "servicios" in comando or "servicio" in comando:
        servicios = sensor_servicios()

        output = "🔧 SERVICIOS URA\n"
        output += "=" * 30 + "\n"

        for nombre, datos in servicios.items():
            icon = "✅" if datos["activo"] else "❌"
            output += f"{icon} {nombre:15} {'ACTIVO' if datos['activo'] else 'CAÍDO'}\n"

        logger.log_ok(output)
        return output

    elif "estado" in comando or "status" in comando:
        # Reporte completo
        red = sensor_red()
        recursos = sensor_recursos()
        servicios = sensor_servicios()

        output = "📊 ESTADO COMPLETO URA\n"
        output += "=" * 35 + "\n\n"

        # Recursos
        output += f"💻 CPU: {recursos['cpu']}% | RAM: {recursos['memoria']}% | Disco: {recursos['disco']}%\n\n"

        # Servicios
        output += "🔧 SERVICIOS:\n"
        for nombre, datos in servicios.items():
            icon = "✅" if datos["activo"] else "❌"
            output += f"  {icon} {nombre}\n"
        output += "\n"

        # Red
        output += "📡 RED:\n"
        for nombre, datos in red.items():
            icon = "✅" if datos["estado"] == "OK" else "❌"
            output += f"  {icon} {nombre}: {datos['estado']}\n"

        logger.log_ok(output)
        return output

    elif "docker" in comando:
        resultado = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = "🐳 DOCKER\n"
        output += "=" * 25 + "\n"
        output += resultado.stdout if resultado.stdout else "No hay contenedores"
        logger.log_ok(output)
        return output

    elif "procesos" in comando or "procs" in comando:
        resultado = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
        lineas = resultado.stdout.splitlines()[:15]
        output = "📋 PROCESOS\n"
        output += "=" * 25 + "\n"
        output += "\n".join(lineas)
        logger.log_ok(output)
        return output

    elif "uptime" in comando or "tiempo" in comando:
        resultado = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
        output = "⏱️ UPTIME\n"
        output += "=" * 25 + "\n"
        output += resultado.stdout
        logger.log_ok(output)
        return output

    elif "temperatura" in comando or "temp" in comando:
        resultado = subprocess.run(["osx-cpu-temp"], capture_output=True, text=True, timeout=5)
        output = "🌡️ TEMPERATURA\n"
        output += "=" * 25 + "\n"
        output += resultado.stdout if resultado.stdout else "No disponible"
        logger.log_ok(output)
        return output

    elif "red" in comando and ("wifi" in comando or "ip" in comando):
        resultado = subprocess.run(
            ["ipconfig", "getifaddr", "en0"], capture_output=True, text=True, timeout=5
        )
        output = "🌐 IP LOCAL\n"
        output += "=" * 25 + "\n"
        output += resultado.stdout.strip()
        logger.log_ok(output)
        return output

    elif "ayuda" in comando or "help" in comando:
        output = """🤖 AGENTE SISTEMAS - Comandos:

• "estado" - Reporte completo
• "red" - Cámaras y red local
• "recursos" - CPU, RAM, disco
• "servicios" - Servicios activos
• "docker" - Contenedores
• "procesos" - Procesos
• "uptime" - Tiempo activo
• "temp" - Temperatura
• "ip" - IP local

Notifica automáticamente si detecta fallos críticos."""

        logger.log_ok(output)
        return output


# ============================================================
# MODO CONTINUO (para testing)
# ============================================================
def modo_continuo(intervalo: int = 60):
    """Modo monitoreo continuo"""
    print(f"🔄 Modo continuo: check cada {intervalo}s")
    print("Ctrl+C para detener")

    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Check...")

            # Check red
            red = sensor_red()
            offline = [n for n, d in red.items() if d["estado"] != "OK"]
            if offline:
                print(f"  ⚠️ Offline: {offline}")
            else:
                print("  ✅ Red OK")

            # Check recursos
            recursos = sensor_recursos()
            print(f"  💻 CPU: {recursos['cpu']}% RAM: {recursos['memoria']}%")

            time.sleep(intervalo)

        except KeyboardInterrupt:
            print("\n⏹️ Detenido")
            break


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        modo_continuo(intervalo=int(sys.argv[2] if len(sys.argv) > 2 else 60))
    else:
        print("=" * 40)
        print("AGENTE SISTEMAS - URA")
        print("=" * 40)

        # Test comando
        print("\n📡 Check red:")
        print(ejecutar("red"))

        print("\n💻 Check recursos:")
        print(ejecutar("recursos"))
