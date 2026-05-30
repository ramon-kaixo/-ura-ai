#!/usr/bin/env python3
"""
Health Check para URA
Monitorización continua de componentes críticos
"""

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class HealthChecker:
    """Monitor de salud para URA"""

    def __init__(self, check_interval: int = 300):  # 5 minutos por defecto
        self.check_interval = check_interval
        self.running = False
        self.log_file = Path(__file__).parent / "logs" / "health_check.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(self.log_file), logging.StreamHandler()],
        )

    def check_ollama(self) -> dict:
        """Verificar si Ollama responde"""
        result = {"service": "Ollama", "status": "unknown", "timestamp": datetime.now().isoformat()}

        try:
            process = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)

            if process.returncode == 0:
                result["status"] = "healthy"
                result["message"] = "Ollama responde correctamente"
                result["models"] = process.stdout.count("\n") - 1  # Contar modelos
            else:
                result["status"] = "unhealthy"
                result["message"] = f"Ollama no responde: {process.stderr}"
        except FileNotFoundError:
            result["status"] = "not_found"
            result["message"] = "Ollama no está instalado"
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["message"] = "Ollama no responde en el tiempo esperado"
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Error verificando Ollama: {e}"

        return result

    def check_redis(self) -> dict:
        """Verificar si Redis está activo"""
        result = {"service": "Redis", "status": "unknown", "timestamp": datetime.now().isoformat()}

        try:
            process = subprocess.run(
                ["redis-cli", "ping"], capture_output=True, text=True, timeout=5
            )

            if "PONG" in process.stdout:
                result["status"] = "healthy"
                result["message"] = "Redis responde correctamente"
            else:
                result["status"] = "unhealthy"
                result["message"] = f"Redis no responde: {process.stderr}"
        except FileNotFoundError:
            result["status"] = "not_found"
            result["message"] = "Redis no está instalado"
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["message"] = "Redis no responde en el tiempo esperado"
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Error verificando Redis: {e}"

        return result

    def check_telegram_bridge(self) -> dict:
        """Verificar si el bridge de Telegram está conectado"""
        result = {
            "service": "Telegram Bridge",
            "status": "unknown",
            "timestamp": datetime.now().isoformat(),
        }

        # Verificar si hay proceso de telegram bridge corriendo
        try:
            process = subprocess.run(
                ["pgrep", "-f", "telegram"], capture_output=True, text=True, timeout=5
            )

            if process.returncode == 0:
                result["status"] = "healthy"
                result["message"] = "Telegram bridge está corriendo"
            else:
                result["status"] = "unhealthy"
                result["message"] = "Telegram bridge no está corriendo"
        except FileNotFoundError:
            result["status"] = "not_found"
            result["message"] = "pgrep no disponible"
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["message"] = "Timeout verificando Telegram bridge"
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Error verificando Telegram bridge: {e}"

        return result

    def check_semantic_memory(self) -> dict:
        """Verificar si la memoria semántica está OK"""
        result = {
            "service": "Semantic Memory",
            "status": "unknown",
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Verificar si el directorio de memoria semántica existe
            memory_dir = Path.home() / ".chroma"
            if memory_dir.exists():
                result["status"] = "healthy"
                result["message"] = "Directorio de memoria semántica existe"
            else:
                result["status"] = "unhealthy"
                result["message"] = "Directorio de memoria semántica no existe"
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Error verificando memoria semántica: {e}"

        return result

    def check_disk_space(self) -> dict:
        """Verificar espacio en disco"""
        result = {
            "service": "Disk Space",
            "status": "unknown",
            "timestamp": datetime.now().isoformat(),
        }

        try:
            import shutil

            total, used, free = shutil.disk_usage(Path.home())

            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            used_percent = (used / total) * 100

            result["free_gb"] = round(free_gb, 2)
            result["total_gb"] = round(total_gb, 2)
            result["used_percent"] = round(used_percent, 2)

            if free_gb > 10:
                result["status"] = "healthy"
                result["message"] = f"Espacio suficiente: {free_gb:.2f} GB libres"
            elif free_gb > 5:
                result["status"] = "warning"
                result["message"] = f"Espacio bajo: {free_gb:.2f} GB libres"
            else:
                result["status"] = "critical"
                result["message"] = f"Espacio crítico: {free_gb:.2f} GB libres"
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Error verificando espacio en disco: {e}"

        return result

    def run_all_checks(self) -> dict:
        """Ejecutar todos los checks"""
        checks = {
            "ollama": self.check_ollama(),
            "redis": self.check_redis(),
            "telegram_bridge": self.check_telegram_bridge(),
            "semantic_memory": self.check_semantic_memory(),
            "disk_space": self.check_disk_space(),
        }

        # Calcular estado general
        statuses = [check["status"] for check in checks.values()]

        if "critical" in statuses or "error" in statuses:
            overall_status = "critical"
        elif "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "healthy"

        result = {
            "overall_status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "checks": checks,
        }

        return result

    def attempt_recovery(self, check_name: str) -> bool:
        """Intentar recuperar un servicio"""
        logger.info(f"Intentando recuperar {check_name}...")

        if check_name == "ollama":
            try:
                subprocess.run(["ollama", "serve"], check=False)
                time.sleep(5)
                return self.check_ollama()["status"] == "healthy"
            except Exception as e:
                logger.error(f"Error recuperando Ollama: {e}")
                return False

        elif check_name == "redis":
            try:
                subprocess.run(["redis-server", "--daemonize yes"], check=False)
                time.sleep(3)
                return self.check_redis()["status"] == "healthy"
            except Exception as e:
                logger.error(f"Error recuperando Redis: {e}")
                return False

        return False

    def monitor_loop(self):
        """Bucle de monitorización continua"""
        logger.info("Iniciando monitorización continua de URA...")

        while self.running:
            # Ejecutar checks
            result = self.run_all_checks()

            # Loggear resultados
            logger.info(f"Estado general: {result['overall_status']}")
            for check_name, check_result in result["checks"].items():
                logger.info(f"  {check_name}: {check_result['status']} - {check_result['message']}")

            # Intentar recuperar servicios críticos
            if result["overall_status"] in ["critical", "unhealthy"]:
                for check_name, check_result in result["checks"].items():
                    if check_result["status"] in ["critical", "unhealthy"]:
                        if check_name in ["ollama", "redis"]:
                            logger.warning(f"Intentando recuperar {check_name}...")
                            self.attempt_recovery(check_name)

            # Guardar resultado en archivo JSON
            try:
                report_file = Path(__file__).parent / "logs" / "health_report.json"
                with open(report_file, "w") as f:
                    json.dump(result, f, indent=2)
            except Exception as e:
                logger.error(f"Error guardando reporte de salud: {e}")

            # Esperar siguiente ciclo
            time.sleep(self.check_interval)

    def start(self):
        """Iniciar monitorización"""
        self.running = True
        logger.info(f"Health checker iniciado (intervalo: {self.check_interval}s)")

    def stop(self):
        """Detener monitorización"""
        self.running = False
        logger.info("Health checker detenido")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Health Check para URA")
    parser.add_argument(
        "--interval", type=int, default=300, help="Intervalo de check en segundos (default: 300)"
    )
    parser.add_argument("--once", action="store_true", help="Ejecutar solo una vez")

    args = parser.parse_args()

    checker = HealthChecker(check_interval=args.interval)

    if args.once:
        # Ejecutar solo una vez
        result = checker.run_all_checks()
        print(json.dumps(result, indent=2))
    else:
        # Ejecutar en modo monitorización continua
        checker.start()
        try:
            checker.monitor_loop()
        except KeyboardInterrupt:
            checker.stop()
            logger.info("Health checker detenido por usuario")
