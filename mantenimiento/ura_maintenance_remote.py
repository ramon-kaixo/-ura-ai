#!/usr/bin/env python3
"""
URA Maintenance Remote - Ejecuta mantenimiento en nodos remotos del enjambre (SEGURE)
"""

import subprocess
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Configuración
DEFAULT_CONFIG = {
    "swarm_devices_path": "/home/ramon/URA/swarm/known_devices.json",
    "log_dir": "/opt/ura/logs/maintenance",
    "ssh_user": "ramon",
    "ssh_timeout": 300,
    "max_parallel": 5,
}


def load_config(config_path: str | None = None) -> dict:
    """Cargar configuración desde archivo"""
    config = DEFAULT_CONFIG.copy()

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path) as f:
                user_config = json.load(f)
                config.update(user_config)
        except (OSError, json.JSONDecodeError) as e:
            logging.warning(f"Error cargando config: {e}")

    return config


CONFIG = load_config(os.environ.get("URA_MAINTENANCE_REMOTE_CONFIG"))

LOG_DIR = Path(CONFIG["log_dir"])
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not os.access(LOG_DIR, os.W_OK):
        raise PermissionError(f"No write access to {LOG_DIR}")
except (PermissionError, OSError):
    LOG_DIR = Path("/tmp/ura_maintenance_logs")
    LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_DIR / f"remote_maintenance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def validate_ip(ip: str) -> bool:
    """Validar formato de dirección IP"""
    pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if not re.match(pattern, ip):
        return False
    # Verificar rango válido
    parts = ip.split(".")
    return all(0 <= int(part) <= 255 for part in parts)


def validate_ssh_user(user: str) -> bool:
    """Validar nombre de usuario SSH"""
    if not user:
        return False
    # Solo permitir caracteres alfanuméricos, guiones y guiones bajos
    return re.match(r"^[a-zA-Z0-9_-]+$", user) is not None


def get_swarm_devices() -> dict:
    """Obtener dispositivos del enjambre"""
    try:
        swarm_path = CONFIG["swarm_devices_path"]
        if not os.path.exists(swarm_path):
            logger.error(f"Archivo de dispositivos no encontrado: {swarm_path}")
            return {}

        with open(swarm_path) as f:
            devices = json.load(f)

        # Validar que sea un diccionario
        if not isinstance(devices, dict):
            logger.error("Formato inválido de dispositivos")
            return {}

        return devices
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON de dispositivos: {e}")
        return {}
    except OSError as e:
        logger.error(f"Error leyendo dispositivos: {e}")
        return {}


def run_remote_maintenance(ip: str, user: str = None) -> dict:
    """Ejecutar mantenimiento en nodo remoto de forma segura"""
    if user is None:
        user = CONFIG["ssh_user"]

    # Validar entrada
    if not validate_ip(ip):
        return _handle_validation_error(ip, "Invalid IP address format")

    if not validate_ssh_user(user):
        return _handle_validation_error(ip, "Invalid SSH username")

    try:
        logger.info(f"Ejecutando mantenimiento en {user}@{ip}")

        # Copiar script usando scp
        local_script = "/home/ramon/URA/mantenimiento/ura_maintenance.py"
        remote_script = "/tmp/ura_maintenance.py"

        if not os.path.exists(local_script):
            return _handle_local_script_error(ip, f"Local script not found: {local_script}")

        result = copy_script_to_remote(ip, user, local_script, remote_script)

        # Ejecutar mantenimiento usando ssh
        output = execute_maintenance_on_remote(ip, user, remote_script)

        if output.returncode == 0:
            logger.info(f"Mantenimiento completado en {ip}")
            return {"ip": ip, "status": "success", "output": output.stdout}
        else:
            logger.error(f"Error en mantenimiento en {ip}: {output.stderr}")
            return {"ip": ip, "status": "error", "error": output.stderr}
    except Exception as e:
        logger.error(f"Error ejecutando mantenimiento en {ip}: {e}")
        return {"ip": ip, "status": "error", "error": str(e)}


def _handle_validation_error(ip: str, error_message: str) -> dict:
    return {"ip": ip, "status": "error", "error": error_message}


def _handle_local_script_error(ip: str, error_message: str) -> dict:
    return {"ip": ip, "status": "error", "error": error_message}


def copy_script_to_remote(
    ip: str, user: str, local_script: str, remote_script: str
) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            ["scp", local_script, f"{user}@{ip}:{remote_script}"],
            check=True,
            timeout=CONFIG["ssh_timeout"],
        )
    except subprocess.TimeoutExpired:
        return _handle_timeout_error(ip, "SCP timeout")
    except subprocess.CalledProcessError as e:
        return _handle_command_error(ip, f"SCP failed: {e}")
    except FileNotFoundError:
        return _handle_command_not_found_error(ip, "SCP command not found")

    return result


def execute_maintenance_on_remote(
    ip: str, user: str, remote_script: str
) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            ["ssh", f"{user}@{ip}", "python3", remote_script],
            capture_output=True,
            text=True,
            timeout=CONFIG["ssh_timeout"],
        )
    except subprocess.TimeoutExpired:
        return _handle_timeout_error(ip, "SSH execution timeout")
    except subprocess.CalledProcessError as e:
        return _handle_command_error(ip, f"SSH execution failed: {e}")
    except FileNotFoundError:
        return _handle_command_not_found_error(ip, "SSH command not found")

    return result


def _handle_timeout_error(ip: str, error_message: str) -> subprocess.CompletedProcess:
    return {"ip": ip, "status": "error", "error": error_message}


def _handle_command_error(ip: str, error_message: str) -> subprocess.CompletedProcess:
    return {"ip": ip, "status": "error", "error": error_message}


def _handle_command_not_found_error(ip: str, error_message: str) -> subprocess.CompletedProcess:
    return {"ip": ip, "status": "error", "error": error_message}


def main():
    """Función principal"""
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
    results_file = (
        LOG_DIR / f"remote_maintenance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    try:
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Resultados guardados en: {results_file}")
    except OSError as e:
        logger.error(f"Error guardando resultados: {e}")

    # Resumen
    success = sum(1 for r in results if r["status"] == "success")
    errors = sum(1 for r in results if r["status"] == "error")
    logger.info(f"Éxitos: {success}/{len(results)}, Errores: {errors}/{len(results)}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
