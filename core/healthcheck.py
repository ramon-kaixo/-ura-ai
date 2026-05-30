#!/usr/bin/env python3
"""
Módulo: core/healthcheck.py
Propósito: Healthcheck completo: verifica Ollama, Redis, PM2 y archivos de salida. Determina estado general.
Dependencias principales: subprocess, pathlib, json, datetime
Reglas especiales: Incluir check_output_files en overall_status. No falsos positivos.
"""

import json
import logging
import requests
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class URAHealthCheck:
    """Verificador de salud del sistema URA"""

    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/tags"
        self.redis_host = "localhost"
        self.redis_port = 6379
        self.pm2_process_name = "ura-operaciones-activas"
        self.output_dir = Path.home() / ".ura" / "output"
        self.alert_sent_recently = False
        self.last_alert_time = None

    def check_ollama(self) -> bool:
        """Verificar si Ollama responde"""
        try:
            response = requests.get(self.ollama_url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama check failed: {e}")
            return False

    def check_redis(self) -> bool:
        """Verificar si Redis responde"""
        try:
            import redis

            r = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)
            r.ping()
            return True
        except ImportError:
            logger.warning("Redis no instalado - saltando verificación")
            return True  # No es crítico si no está instalado
        except Exception as e:
            logger.error(f"Redis check failed: {e}")
            return False

    def check_pm2(self) -> bool:
        """Verificar si PM2 tiene el proceso registrado"""
        try:
            result = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return False

            processes = json.loads(result.stdout)
            for proc in processes:
                if proc.get("name") == self.pm2_process_name:
                    return proc.get("status") == "online"
            return False
        except Exception as e:
            logger.error(f"PM2 check failed: {e}")
            return False

    def check_output_files(self) -> bool:
        """Verificar si archivos de salida se actualizaron en última hora"""
        try:
            if not self.output_dir.exists():
                return True  # No es crítico si no existe aún

            one_hour_ago = datetime.now().timestamp() - 3600
            recent_files = [
                f for f in self.output_dir.glob("*.json") if f.stat().st_mtime > one_hour_ago
            ]
            return len(recent_files) > 0
        except Exception as e:
            logger.error(f"Output files check failed: {e}")
            return True  # No es crítico

    def run_all_checks(self) -> dict:
        """Ejecutar todas las verificaciones"""
        results = {
            "ollama": self.check_ollama(),
            "redis": self.check_redis(),
            "pm2": self.check_pm2(),
            "output_files": self.check_output_files(),
            "timestamp": datetime.now().isoformat(),
        }

        # Determinar estado general
        results["overall_status"] = all(
            [results["ollama"], results["redis"], results["pm2"], results["output_files"]]
        )

        return results

    def send_alert_if_needed(self, results: dict):
        """Enviar alerta por Telegram si algo falla"""
        if not results["overall_status"]:
            # Evitar spam de alertas (máximo 1 cada 10 minutos)
            if self.last_alert_time:
                time_since_last = datetime.now().timestamp() - self.last_alert_time
                if time_since_last < 600:  # 10 minutos
                    return

            try:
                from core.telegram_security_bridge import get_telegram_security_bridge

                bridge = get_telegram_security_bridge()

                failed_services = [
                    k
                    for k, v in results.items()
                    if not v and k not in ["timestamp", "overall_status"]
                ]
                alert_message = f"⚠️ ALERTA URA - Servicios fallando: {', '.join(failed_services)}"

                bridge.send_message(alert_message)
                self.last_alert_time = datetime.now().timestamp()
                logger.warning(f"Alerta enviada: {alert_message}")
            except Exception as e:
                logger.error(f"Error enviando alerta: {e}")


def main():
    """Función principal para ejecutar healthcheck"""
    healthcheck = URAHealthCheck()
    results = healthcheck.run_all_checks()

    logger.info(f"Healthcheck results: {results}")
    healthcheck.send_alert_if_needed(results)

    return results["overall_status"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
