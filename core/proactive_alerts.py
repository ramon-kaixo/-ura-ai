#!/usr/bin/env python3
"""
Sistema de Alertas Proactivas - URA App
Detecta problemas antes de que ocurran y envía alertas
"""

import logging
import time
from datetime import datetime

import psutil
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProactiveAlerts:
    """Sistema de alertas proactivas"""

    def __init__(self):
        self.umbrales = {
            "cpu_percent": 80,
            "ram_percent": 80,
            "disk_percent": 20,
            "ollama_latency": 5,  # segundos
        }
        self.alertas_enviadas = {}
        self.cooldown = 3600  # 1 hora entre alertas del mismo tipo

    def verificar_cpu(self):
        """Verificar uso de CPU"""
        cpu_percent = psutil.cpu_percent(interval=1)

        if cpu_percent > self.umbrales["cpu_percent"]:
            return self.enviar_alerta("cpu", f"CPU alto: {cpu_percent}%")

        return None

    def verificar_ram(self):
        """Verificar uso de RAM"""
        ram = psutil.virtual_memory()
        ram_percent = ram.percent

        if ram_percent > self.umbrales["ram_percent"]:
            return self.enviar_alerta("ram", f"RAM alta: {ram_percent}%")

        return None

    def verificar_disco(self):
        """Verificar espacio en disco"""
        disco = psutil.disk_usage("/")
        disco_percent = disco.percent
        disco_libre_gb = disco.free / (1024**3)

        if disco_percent < self.umbrales["disk_percent"]:
            return self.enviar_alerta("disco", f"Disco bajo: {disco_libre_gb:.1f}GB libre")

        return None

    def verificar_ollama(self):
        """Verificar latencia de Ollama"""
        try:
            inicio = time.time()
            response = requests.get("http://localhost:11434/api/tags", timeout=10)
            latencia = time.time() - inicio

            if latencia > self.umbrales["ollama_latency"]:
                return self.enviar_alerta("ollama", f"Ollama lento: {latencia:.2f}s")

            if response.status_code != 200:
                return self.enviar_alerta("ollama", f"Ollama error: {response.status_code}")

        except Exception as e:
            return self.enviar_alerta("ollama", f"Ollama no responde: {e}")

        return None

    def verificar_redis(self):
        """Verificar conexión Redis"""
        try:
            import redis

            r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
            r.ping()
            return None
        except Exception as e:
            return self.enviar_alerta("redis", f"Redis no responde: {e}")

    def enviar_alerta(self, tipo, mensaje):
        """Enviar alerta si no se ha enviado recientemente"""
        ahora = datetime.now().timestamp()

        # Verificar cooldown
        if tipo in self.alertas_enviadas:
            tiempo_ultimo = self.alertas_enviadas[tipo]
            if ahora - tiempo_ultimo < self.cooldown:
                return None

        # Enviar alerta
        logger.warning(f"ALERTA PROACTIVA [{tipo}]: {mensaje}")
        self.alertas_enviadas[tipo] = ahora

        # Aquí podrías enviar a Telegram/Discord
        # self.telegram_bridge.enviar_alerta(mensaje)

        return {"tipo": tipo, "mensaje": mensaje, "timestamp": datetime.now().isoformat()}

    def verificar_todo(self):
        """Verificar todos los sistemas"""
        alertas = []

        alertas.append(self.verificar_cpu())
        alertas.append(self.verificar_ram())
        alertas.append(self.verificar_disco())
        alertas.append(self.verificar_ollama())
        alertas.append(self.verificar_redis())

        # Filtrar None
        alertas = [a for a in alertas if a is not None]

        return alertas


# Instancia global
proactive_alerts = ProactiveAlerts()

if __name__ == "__main__":
    print("Verificando sistemas proactivamente...")
    alertas = proactive_alerts.verificar_todo()

    if alertas:
        print(f"Se detectaron {len(alertas)} alertas:")
        for alerta in alertas:
            print(f"  - {alerta}")
    else:
        print("Todos los sistemas OK")
