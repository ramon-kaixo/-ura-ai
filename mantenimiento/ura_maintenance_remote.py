import os  # noqa: INP001

#!/usr/bin/env python3  # noqa: EXE005
"""
URA Maintenance Remote - Ejecuta mantenimiento en nodos remotos del enjambre (SEGURE)
"""

import json
import logging
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

# Configuración
DEFAULT_CONFIG = {
    "swarm_devices_path": "/home/ramon/URA/swarm/known_devices.json",
    "log_dir": "/opt/ura/logs/maintenance",
    "ssh_user": "ramon",
    "ssh_timeout": 300,
    "max_parallel": 5,
}


def load_config(config_path: str | None = None) -> dict:
    """Cargar configuración desde archivo."""
    config = DEFAULT_CONFIG.copy()

    if config_path and Path(config_path).exists():
        try:
            with open(config_path) as f:  # noqa: PTH123
                user_config = json.load(f)
                config.update(user_config)
        except (OSError, json.JSONDecodeError) as e:
            logging.warning(f"Error cargando config: {e}")  # noqa: LOG015

    return config


CONFIG = load_config(os.environ.get("URA_MAINTENANCE_REMOTE_CONFIG"))

LOG_DIR = Path(CONFIG["log_dir"])
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not os.access(LOG_DIR, os.W_OK):
        msg = f"No write access to {LOG_DIR}"
        raise PermissionError(msg)
except (PermissionError, OSError):
    LOG_DIR = Path("/tmp/ura_maintenance_logs")  # noqa: S108
    LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"remote_maintenance_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def validate_ip(ip: str) -> bool:
    """Validar formato de dirección IP."""
    pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if not re.match(pattern, ip):
        return False
    # Verificar rango válido
    parts = ip.split(".")
    return all(0 <= int(part) <= 255 for part in parts)


def validate_ssh_user(user: str) -> bool:
    """Validar nombre de usuario SSH."""
    if not user:
        return False
    # Solo permitir caracteres alfanuméricos, guiones y guiones bajos
    return re.match(r"^[a-zA-Z0-9_-]+$", user) is not None


def get_swarm_devices() -> dict:
    """Obtener dispositivos del enjambre."""
    try:
        swarm_path = CONFIG["swarm_devices_path"]
        if not Path(swarm_path).exists():
            logger.error(f"Archivo de dispositivos no encontrado: {swarm_path}")
            return {}

        with open(swarm_path) as f:  # noqa: PTH123
            devices = json.load(f)

        # Validar que sea un diccionario
        if not isinstance(devices, dict):
            logger.error("Formato inválido de dispositivos")
            return {}

        return devices
    except json.JSONDecodeError as e:
        logger.exception(f"Error parseando JSON de dispositivos: {e}")
        return {}
    except OSError as e:
        logger.exception(f"Error leyendo dispositivos: {e}")
        return {}


def run_remote_maintenance(ip: str, user: str | None = None) -> dict:  # noqa: C901, PLR0911
    """Ejecutar mantenimiento en nodo remoto de forma segura."""
    if user is None:
        user = CONFIG["ssh_user"]

    # Validar entrada
    if not validate_ip(ip):
        return {
            "ip": ip,
            "status": "error",
            "error": "Invalid IP address format",
        }

    if not validate_ssh_user(user):
        return {
            "ip": ip,
            "status": "error",
            "error": "Invalid SSH username",
        }

    try:
        logger.info(f"Ejecutando mantenimiento en {user}@{ip}")

        # Usar subprocess sin shell=True para evitar inyección
        # Copiar script usando scp con argumentos separados
        local_script = "/home/ramon/URA/mantenimiento/ura_maintenance.py"
        remote_script = "/tmp/ura_maintenance.py"  # noqa: S108

        if not Path(local_script).exists():
            return {
                "ip": ip,
                "status": "error",
                "error": f"Local script not found: {local_script}",
            }

        try:
            subprocess.run(  # noqa: S603
                ["scp", local_script, f"{user}@{ip}:{remote_script}"],  # noqa: S607
                check=True,
                timeout=CONFIG["ssh_timeout"],
            )
        except subprocess.TimeoutExpired:
            return {
                "ip": ip,
                "status": "error",
                "error": "SCP timeout",
            }
        except subprocess.CalledProcessError as e:
            return {
                "ip": ip,
                "status": "error",
                "error": f"SCP failed: {e}",
            }
        except FileNotFoundError:
            return {
                "ip": ip,
                "status": "error",
                "error": "SCP command not found",
            }

        # Ejecutar mantenimiento usando ssh sin shell=True
        try:
            result = subprocess.run(  # noqa: S603
                ["ssh", f"{user}@{ip}", "python3", remote_script],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=CONFIG["ssh_timeout"],
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "ip": ip,
                "status": "error",
                "error": "SSH execution timeout",
            }
        except subprocess.CalledProcessError as e:
            return {
                "ip": ip,
                "status": "error",
                "error": f"SSH execution failed: {e}",
            }
        except FileNotFoundError:
            return {
                "ip": ip,
                "status": "error",
                "error": "SSH command not found",
            }

        if result.returncode == 0:
            logger.info(f"Mantenimiento completado en {ip}")
            return {
                "ip": ip,
                "status": "success",
                "output": result.stdout,
            }
        logger.error(f"Error en mantenimiento en {ip}: {result.stderr}")
        return {
            "ip": ip,
            "status": "error",
            "error": result.stderr,
        }
    except Exception as e:
        logger.exception(f"Error ejecutando mantenimiento en {ip}: {e}")
        return {
            "ip": ip,
            "status": "error",
            "error": str(e),
        }


def main() -> int:
    """Función principal."""
    logger.info("Iniciando mantenimiento remoto del enjambre")

    devices = get_swarm_devices()
    if not devices:
        logger.error("No se encontraron dispositivos en el enjambre")
        return 1

    results = []

    for ip, device_info in devices.items():
        if device_info.get("status") == "active":
            result = run_remote_maintenance(ip)
            results.append(result)
        else:
            logger.info(f"Omitiendo dispositivo inactivo: {ip}")

    # Guardar resultados
    results_file = LOG_DIR / f"remote_maintenance_results_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(results_file, "w") as f:  # noqa: PTH123
            json.dump(results, f, indent=2)
        logger.info(f"Resultados guardados en: {results_file}")
    except OSError as e:
        logger.exception(f"Error guardando resultados: {e}")

    # Resumen
    success = sum(1 for r in results if r["status"] == "success")
    errors = sum(1 for r in results if r["status"] == "error")
    logger.info(f"Éxitos: {success}/{len(results)}, Errores: {errors}/{len(results)}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
