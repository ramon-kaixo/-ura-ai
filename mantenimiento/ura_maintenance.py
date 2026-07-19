#!/usr/bin/env python3
"""URA Maintenance System - Sistema de mantenimiento automatizado (SEGURE)
Escanea y limpia sistemas del enjambre URA de forma segura
"""

import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path

# Configuración por defecto (puede sobrescribirse con archivo de config)
DEFAULT_CONFIG = {
    "log_dir": "/opt/ura/logs/maintenance",
    "exclude_patterns": [
        "*.db",
        "*.sqlite",
        "*.sqlite-wal",  # Bases de datos
        "*.key",
        "*.pem",
        "*.crt",  # Certificados y claves
        "*.env",
        "*.secret",  # Archivos de configuración sensible
        "/home/*/URA/",  # Directorio URA principal
        "/home/*/projects/",  # Proyectos de usuario
        "/home/*/Documents/",  # Documentos
        "/home/*/Desktop/",  # Escritorio
        "/home/*/Downloads/",  # Descargas (por seguridad)
        "/opt/ura/",  # Directorio URA
        "/etc/",  # Configuración del sistema
        "/var/lib/",  # Datos del sistema
    ],
    "thresholds": {
        "docker_images": 10,  # Limpiar si > 10GB de imágenes
        "docker_volumes": 5,  # Limpiar si > 5GB de volúmenes
        "cache_size": 2,  # Limpiar si > 2GB de cache
        "log_size": 1,  # Limpiar si > 1GB de logs
    },
    "retention_days": {
        "logs": 7,  # Mantener logs 7 días
        "cache": 30,  # Mantener cache 30 días
        "docker_build": 7,  # Mantener build cache 7 días
    },
    "allowed_temp_dirs": ["/tmp", "/var/tmp"],
    "allowed_log_dirs": ["/var/log", "/opt/ura/logs"],
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


# Cargar configuración
CONFIG = load_config(os.environ.get("URA_MAINTENANCE_CONFIG"))

# Configuración de logging
LOG_DIR = Path(CONFIG["log_dir"])
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Verificar permisos de escritura
    if not os.access(LOG_DIR, os.W_OK):
        raise PermissionError(f"No write access to {LOG_DIR}")
except (PermissionError, OSError):
    # Fallback a directorio temporal
    LOG_DIR = Path("/tmp/ura_maintenance_logs")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.warning(f"Using fallback log directory: {LOG_DIR}")

LOG_FILE = LOG_DIR / f"maintenance_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class SecurityValidator:
    """Validador de seguridad para operaciones de archivo"""

    def __init__(self, config: dict):
        self.config = config
        self.current_uid = os.getuid()
        self.current_gid = os.getgid()

    def is_safe_to_delete(self, file_path: str) -> tuple[bool, str]:
        """Verificar si es seguro borrar un archivo"""
        path = Path(file_path)

        # Verificar symlink
        if path.is_symlink():
            return False, f"Symlink detected: {file_path}"

        # Verificar ownership
        try:
            stat_info = path.stat()
            if self.current_uid not in (stat_info.st_uid, 0):
                return False, f"Not owner: {file_path} (uid {stat_info.st_uid})"
        except OSError as e:
            return False, f"Cannot stat: {file_path} ({e})"

        # Verificar patrones de exclusión
        if self._matches_exclude_pattern(str(path)):
            return False, f"Matches exclude pattern: {file_path}"

        # Verificar directory traversal
        real_path = os.path.realpath(str(path))
        if not self._is_in_allowed_dir(real_path):
            return False, f"Outside allowed directories: {file_path}"

        return True, "Safe"

    def _matches_exclude_pattern(self, path: str) -> bool:
        """Verificar si path coincide con patrones de exclusión"""
        for pattern in self.config["exclude_patterns"]:
            if fnmatch(path, pattern) or fnmatch(os.path.basename(path), pattern):
                return True
        return False

    def _is_in_allowed_dir(self, path: str) -> bool:
        """Verificar si path está dentro de directorios permitidos"""
        allowed_dirs = self.config.get("allowed_temp_dirs", []) + self.config.get("allowed_log_dirs", [])

        return any(path.startswith(os.path.realpath(allowed_dir)) for allowed_dir in allowed_dirs)


class MaintenanceConfig:
    """Configuración de mantenimiento"""

    def __init__(self, config: dict):
        self.exclude_patterns = config["exclude_patterns"]
        self.thresholds = config["thresholds"]
        self.retention_days = config["retention_days"]
        self.allowed_temp_dirs = config["allowed_temp_dirs"]
        self.allowed_log_dirs = config["allowed_log_dirs"]


class SystemCleaner:
    """Clase base para limpieza de sistemas"""

    def __init__(self, config: MaintenanceConfig, validator: SecurityValidator):
        self.config = config
        self.validator = validator
        self.space_freed = 0
        self.operations = []

    def get_disk_usage(self, path: str = "/") -> dict:
        """Obtener uso de disco"""
        try:
            usage = shutil.disk_usage(path)
            return {
                "total": usage.total / (1024**3),
                "used": usage.used / (1024**3),
                "free": usage.free / (1024**3),
                "percent": (usage.used / usage.total) * 100,
            }
        except OSError as e:
            logger.error(f"Error obteniendo uso de disco: {e}")
            return {}

    def should_clean(self, size_gb: float, threshold: str) -> bool:
        """Determinar si se debe limpiar basado en umbral"""
        threshold_gb = self.config.thresholds.get(threshold, 0)
        return size_gb > threshold_gb

    def record_operation(self, operation: str, size_freed: float):
        """Registrar operación de limpieza"""
        self.operations.append(
            {
                "operation": operation,
                "size_freed_gb": size_freed,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        self.space_freed += size_freed
        logger.info(f"Operación: {operation} - Liberado: {size_freed:.2f}GB")

    def safe_remove(self, file_path: str) -> bool:
        """Eliminar archivo de forma segura"""
        is_safe, reason = self.validator.is_safe_to_delete(file_path)
        if not is_safe:
            logger.debug(f"Skipping {file_path}: {reason}")
            return False

        try:
            os.remove(file_path)
            return True
        except OSError as e:
            logger.warning(f"Error removing {file_path}: {e}")
            return False

    def safe_rmtree(self, dir_path: str) -> bool:
        """Eliminar directorio de forma segura"""
        is_safe, reason = self.validator.is_safe_to_delete(dir_path)
        if not is_safe:
            logger.debug(f"Skipping {dir_path}: {reason}")
            return False

        try:
            shutil.rmtree(dir_path)
            return True
        except OSError as e:
            logger.warning(f"Error removing {dir_path}: {e}")
            return False


class LinuxCleaner(SystemCleaner):
    """Limpiador específico para Linux"""

    def __init__(self, config: MaintenanceConfig, validator: SecurityValidator):
        super().__init__(config, validator)
        self.os_type = "linux"

    def clean_docker(self) -> float:
        """Limpiar Docker"""
        try:
            logger.info("Limpiando Docker...")

            # Verificar si docker está instalado
            try:
                subprocess.run(["docker", "--version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.info("Docker no instalado, saltando")
                return 0

            result = subprocess.run(
                ["docker", "system", "prune", "-a", "--volumes", "-f"],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,  # 5 minutos timeout
            )

            if result.returncode == 0:
                # Extraer espacio liberado del output con regex
                match = re.search(r"Total reclaimed space:\s+([\d.]+)\s*(GB|MB)", result.stdout)
                if match:
                    size = float(match.group(1))
                    if match.group(2) == "MB":
                        size /= 1024
                    self.record_operation("docker_prune", size)
                    return size
            return 0
        except subprocess.TimeoutExpired:
            logger.error("Docker prune timeout")
            return 0
        except Exception as e:
            logger.error(f"Error limpiando Docker: {e}")
            return 0

    def clean_apt_cache(self) -> float:
        """Limpiar cache de apt"""
        try:
            logger.info("Limpiando cache de apt...")

            # Verificar si apt está disponible
            if not shutil.which("apt-get"):
                logger.info("apt-get no disponible, saltando")
                return 0

            before = self.get_disk_usage()

            # Usar -y para evitar prompts (ya incluye non-interactive)
            subprocess.run(
                ["sudo", "apt-get", "autoremove", "-y"],
                check=True,
                timeout=300,
            )
            subprocess.run(
                ["sudo", "apt-get", "clean"],
                check=True,
                timeout=300,
            )

            after = self.get_disk_usage()
            freed = before.get("used", 0) - after.get("used", 0)
            if freed > 0:
                self.record_operation("apt_cache", freed)
            return freed
        except subprocess.TimeoutExpired:
            logger.error("apt-cache cleanup timeout")
            return 0
        except subprocess.CalledProcessError as e:
            logger.error(f"Error ejecutando apt: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error limpiando apt: {e}")
            return 0

    def clean_pip_cache(self) -> float:
        """Limpiar cache de pip"""
        try:
            logger.info("Limpiando cache de pip...")

            # Verificar si pip está disponible
            if not shutil.which("pip3"):
                logger.info("pip3 no disponible, saltando")
                return 0

            # Medir espacio antes
            pip_cache_dir = Path.home() / ".cache" / "pip"
            before_size = 0
            if pip_cache_dir.exists():
                before_size = sum(f.stat().st_size for f in pip_cache_dir.rglob("*") if f.is_file()) / (1024**3)

            result = subprocess.run(
                ["pip3", "cache", "purge"],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            if result.returncode == 0:
                # Medir espacio después
                after_size = 0
                if pip_cache_dir.exists():
                    after_size = sum(f.stat().st_size for f in pip_cache_dir.rglob("*") if f.is_file()) / (1024**3)

                freed = before_size - after_size
                if freed > 0:
                    self.record_operation("pip_cache", freed)
                return freed
            return 0
        except subprocess.TimeoutExpired:
            logger.error("pip cache purge timeout")
            return 0
        except Exception as e:
            logger.error(f"Error limpiando pip: {e}")
            return 0

    def clean_old_logs(self) -> float:
        """Limpiar logs antiguos"""
        try:
            logger.info("Limpiando logs antiguos...")

            total_freed = 0
            retention_days = self.config.retention_days["logs"]

            for log_dir in self.config.allowed_log_dirs:
                if os.path.exists(log_dir):
                    for root, _dirs, files in os.walk(log_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                file_age = (datetime.now(UTC).timestamp() - os.path.getmtime(file_path)) / 86400
                                if file_age > retention_days and file.endswith(".log"):
                                    if self.safe_remove(file_path):
                                        size = os.path.getsize(file_path) / (1024**3)
                                        total_freed += size
                            except OSError:
                                pass

            if total_freed > 0:
                self.record_operation("old_logs", total_freed)
            return total_freed
        except Exception as e:
            logger.error(f"Error limpiando logs: {e}")
            return 0

    def clean_temp_files(self) -> float:
        """Limpiar archivos temporales"""
        try:
            logger.info("Limpiando archivos temporales...")

            total_freed = 0
            for temp_dir in self.config.allowed_temp_dirs:
                if os.path.exists(temp_dir):
                    for item in os.listdir(temp_dir):
                        item_path = os.path.join(temp_dir, item)
                        try:
                            if os.path.isfile(item_path) and self.safe_remove(item_path):
                                size = os.path.getsize(item_path) / (1024**3)
                                total_freed += size
                        except OSError:
                            pass

            if total_freed > 0:
                self.record_operation("temp_files", total_freed)
            return total_freed
        except Exception as e:
            logger.error(f"Error limpiando temporales: {e}")
            return 0


class MacCleaner(SystemCleaner):
    """Limpiador específico para macOS"""

    def __init__(self, config: MaintenanceConfig, validator: SecurityValidator):
        super().__init__(config, validator)
        self.os_type = "macos"
        self.user_home = Path.home()

    def clean_docker(self) -> float:
        """Limpiar Docker en Mac"""
        try:
            logger.info("Limpiando Docker en Mac...")

            if not shutil.which("docker"):
                logger.info("Docker no instalado, saltando")
                return 0

            result = subprocess.run(
                ["docker", "system", "prune", "-a", "--volumes", "-f"],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            if result.returncode == 0:
                match = re.search(r"Total reclaimed space:\s+([\d.]+)\s*(GB|MB)", result.stdout)
                if match:
                    size = float(match.group(1))
                    if match.group(2) == "MB":
                        size /= 1024
                    self.record_operation("docker_prune", size)
                    return size
            return 0
        except subprocess.TimeoutExpired:
            logger.error("Docker prune timeout")
            return 0
        except Exception as e:
            logger.error(f"Error limpiando Docker: {e}")
            return 0

    def clean_brew_cache(self) -> float:
        """Limpiar cache de Homebrew"""
        try:
            logger.info("Limpiando cache de Homebrew...")

            if not shutil.which("brew"):
                logger.info("Homebrew no instalado, saltando")
                return 0

            result = subprocess.run(
                ["brew", "cleanup", "--prune=all"],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            if result.returncode == 0:
                match = re.search(r"freed approximately\s+([\d.]+)\s*(GB|MB)", result.stdout)
                if match:
                    size = float(match.group(1))
                    if match.group(2) == "MB":
                        size /= 1024
                    self.record_operation("brew_cache", size)
                    return size
            return 0
        except subprocess.TimeoutExpired:
            logger.error("brew cleanup timeout")
            return 0
        except Exception as e:
            logger.error(f"Error limpiando brew: {e}")
            return 0

    def clean_pip_cache(self) -> float:
        """Limpiar cache de pip"""
        try:
            logger.info("Limpiando cache de pip...")

            if not shutil.which("pip3"):
                logger.info("pip3 no disponible, saltando")
                return 0

            pip_cache_dir = self.user_home / ".cache" / "pip"
            before_size = 0
            if pip_cache_dir.exists():
                before_size = sum(f.stat().st_size for f in pip_cache_dir.rglob("*") if f.is_file()) / (1024**3)

            result = subprocess.run(
                ["pip3", "cache", "purge"],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            if result.returncode == 0:
                after_size = 0
                if pip_cache_dir.exists():
                    after_size = sum(f.stat().st_size for f in pip_cache_dir.rglob("*") if f.is_file()) / (1024**3)

                freed = before_size - after_size
                if freed > 0:
                    self.record_operation("pip_cache", freed)
                return freed
            return 0
        except subprocess.TimeoutExpired:
            logger.error("pip cache purge timeout")
            return 0
        except Exception as e:
            logger.error(f"Error limpiando pip: {e}")
            return 0

    def clean_application_caches(self) -> float:
        """Limpiar caches de aplicaciones"""
        try:
            logger.info("Limpiando caches de aplicaciones...")

            cache_dirs = [
                self.user_home / "Library" / "Caches",
                self.user_home / "Library" / "Application Support" / "Google" / "Chrome",
            ]

            total_freed = 0
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    for item in cache_dir.iterdir():
                        try:
                            if item.is_dir():
                                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file()) / (1024**3)
                                if self.safe_rmtree(str(item)):
                                    total_freed += size
                        except OSError:
                            pass

            if total_freed > 0:
                self.record_operation("app_caches", total_freed)
            return total_freed
        except Exception as e:
            logger.error(f"Error limpiando caches: {e}")
            return 0

    def clean_logs(self) -> float:
        """Limpiar logs de aplicaciones"""
        try:
            logger.info("Limpiando logs de aplicaciones...")

            log_dirs = [
                self.user_home / "Library" / "Logs",
                self.user_home / "Library" / "Group Containers" / "group.net.whatsapp.WhatsApp.shared" / "Logs",
            ]

            total_freed = 0
            retention_days = self.config.retention_days["logs"]

            for log_dir in log_dirs:
                if log_dir.exists():
                    for log_file in log_dir.rglob("*.log"):
                        try:
                            file_age = (datetime.now(UTC).timestamp() - log_file.stat().st_mtime) / 86400
                            if file_age > retention_days:
                                if self.safe_remove(str(log_file)):
                                    size = log_file.stat().st_size / (1024**3)
                                    total_freed += size
                        except OSError:
                            pass

            if total_freed > 0:
                self.record_operation("app_logs", total_freed)
            return total_freed
        except Exception as e:
            logger.error(f"Error limpiando logs: {e}")
            return 0


class MaintenanceOrchestrator:
    """Orquestador de mantenimiento para el enjambre"""

    def __init__(self):
        self.config = MaintenanceConfig(CONFIG)
        self.validator = SecurityValidator(CONFIG)
        self.cleaner = self._get_cleaner()
        self.results = {}

    def _get_cleaner(self) -> SystemCleaner:
        """Obtener limpiador apropiado para el sistema"""
        system = platform.system().lower()
        if system == "linux":
            return LinuxCleaner(self.config, self.validator)
        if system == "darwin":
            return MacCleaner(self.config, self.validator)
        raise ValueError(f"Sistema no soportado: {system}")

    def run_maintenance(self) -> dict:
        """Ejecutar mantenimiento completo"""
        logger.info(f"Iniciando mantenimiento en {platform.system()}")

        # Estado inicial
        initial_usage = self.cleaner.get_disk_usage()
        logger.info(
            f"Espacio inicial: {initial_usage.get('used', 0):.2f}GB / {initial_usage.get('total', 0):.2f}GB ({initial_usage.get('percent', 0):.1f}%)",
        )

        # Ejecutar limpiezas según sistema
        if isinstance(self.cleaner, LinuxCleaner):
            self.cleaner.clean_docker()
            self.cleaner.clean_apt_cache()
            self.cleaner.clean_pip_cache()
            self.cleaner.clean_old_logs()
            self.cleaner.clean_temp_files()
        elif isinstance(self.cleaner, MacCleaner):
            self.cleaner.clean_docker()
            self.cleaner.clean_brew_cache()
            self.cleaner.clean_pip_cache()
            self.cleaner.clean_application_caches()
            self.cleaner.clean_logs()

        # Estado final
        final_usage = self.cleaner.get_disk_usage()
        logger.info(
            f"Espacio final: {final_usage.get('used', 0):.2f}GB / {final_usage.get('total', 0):.2f}GB ({final_usage.get('percent', 0):.1f}%)",
        )

        # Resultados
        self.results = {
            "system": platform.system(),
            "hostname": platform.node(),
            "initial_usage": initial_usage,
            "final_usage": final_usage,
            "space_freed_gb": self.cleaner.space_freed,
            "operations": self.cleaner.operations,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Guardar resultados
        self._save_results()

        return self.results

    def _save_results(self):
        """Guardar resultados en archivo JSON"""
        results_file = LOG_DIR / f"maintenance_results_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(results_file, "w") as f:
                json.dump(self.results, f, indent=2)
            logger.info(f"Resultados guardados en: {results_file}")
        except OSError as e:
            logger.error(f"Error guardando resultados: {e}")


def main():
    """Función principal"""
    try:
        orchestrator = MaintenanceOrchestrator()
        results = orchestrator.run_maintenance()

        logger.info(f"Mantenimiento completado. Espacio liberado: {results['space_freed_gb']:.2f}GB")
        return 0
    except Exception as e:
        logger.error(f"Error en mantenimiento: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
