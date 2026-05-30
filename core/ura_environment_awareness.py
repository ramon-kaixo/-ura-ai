#!/usr/bin/env python3
"""
Conciencia del Entorno del Sistema de URA - Nivel 21

URA tiene conocimiento de su entorno:
- Archivos y directorios disponibles
- Procesos en ejecución
- Conexiones de red
"""

import json
import logging
import psutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from core.ura_config import config
from core.ura_monitoring import get_ura_monitoring

logger = logging.getLogger(__name__)
monitor = get_ura_monitoring()

ENVIRONMENT_AWARENESS_PATH = Path.home() / ".ura" / "environment_awareness.json"
ENVIRONMENT_AWARENESS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class EnvironmentInfo:
    """Información del entorno."""

    scan_time: str
    directories: list[str]
    files_count: int
    processes_count: int
    network_connections: int
    disk_free_gb: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentInfo":
        return cls(**data)


class URAEnvironmentAwareness:
    """Gestor de conciencia del entorno de URA."""

    def __init__(self):
        self.environment_info = self._load_environment_info()

    def _load_environment_info(self) -> EnvironmentInfo:
        """Cargar información del entorno desde disco."""
        if ENVIRONMENT_AWARENESS_PATH.exists():
            try:
                with open(ENVIRONMENT_AWARENESS_PATH) as f:
                    data = json.load(f)
                    return EnvironmentInfo.from_dict(data)
            except Exception as e:
                logger.error(f"Error cargando información del entorno: {e}")

        return self._scan_environment()

    def _scan_environment(self) -> EnvironmentInfo:
        """Escanear el entorno del sistema con límites de performance."""
        import time

        start = time.time()

        try:
            # Configurar directorios
            directories = [Path.home(), Path.cwd(), Path("/"), Path("/tmp")]

            # Contar archivos con límites
            env_config = config.get_env_config()
            max_depth = env_config["max_depth"]
            max_files = env_config["max_files"]

            files_count = 0
            for directory in directories:
                try:
                    for depth in range(max_depth + 1):
                        if files_count >= max_files:
                            break
                        pattern = "*/" * depth + "*"
                        try:
                            for _ in Path(directory).glob(pattern):
                                if _.is_file():
                                    files_count += 1
                                    if files_count >= max_files:
                                        break
                        except Exception as e:
                            logger.warning(f"Error silencioso en environment_awareness.scan: {e}")
                            # fallback: continuar
                except Exception as e:
                    logger.warning(f"Error silencioso en environment_awareness.scan_outer: {e}")
                    # fallback: continuar

            # Contar procesos
            processes_count = len(psutil.pids())

            # Conexiones de red (con manejo de permisos)
            network_connections = 0
            try:
                network_connections = len(psutil.net_connections())
            except (psutil.AccessDenied, PermissionError):
                logger.warning("Permisos insuficientes para leer conexiones de red")
                monitor.log_error(
                    "environment_awareness",
                    "PermissionError",
                    "Permisos insuficientes para leer conexiones de red",
                )

            # Uso de disco
            disk_usage = psutil.disk_usage("/")
            disk_free_gb = disk_usage.free / (1024**3)

            duration = time.time() - start
            monitor.log_performance("environment_awareness", "scan_environment", duration)

            return EnvironmentInfo(
                scan_time=datetime.now().isoformat(),
                directories=[str(d) for d in directories],
                files_count=files_count,
                processes_count=processes_count,
                network_connections=network_connections,
                disk_free_gb=disk_free_gb,
            )
        except Exception as e:
            monitor.log_error("environment_awareness", "ScanError", str(e))
            raise

    def _save_environment_info(self):
        """Guardar información del entorno a disco."""
        with open(ENVIRONMENT_AWARENESS_PATH, "w") as f:
            json.dump(self.environment_info.to_dict(), f, indent=2)

    def refresh_environment_info(self):
        """Actualizar información del entorno."""
        self.environment_info = self._scan_environment()
        self._save_environment_info()

    def get_environment_context(self) -> str:
        """Genera contexto del entorno para el system prompt."""
        context_parts = ["CONCIENCIA DEL ENTORNO DEL SISTEMA:"]
        context_parts.append(
            f"- Directorios monitoreados: {len(self.environment_info.directories)}"
        )
        context_parts.append(f"- Archivos totales: {self.environment_info.files_count}")
        context_parts.append(f"- Procesos en ejecución: {self.environment_info.processes_count}")
        context_parts.append(f"- Conexiones de red: {self.environment_info.network_connections}")

        context_parts.append(f"- Disco libre: {self.environment_info.disk_free_gb:.1f} GB")

        return "\n".join(context_parts) + "\n"

    def get_available_directories(self) -> list[str]:
        """Obtener directorios disponibles."""
        return self.environment_info.directories

    def get_running_processes(self) -> list[str]:
        """Obtener nombres de procesos en ejecución."""
        processes = []
        for pid in psutil.pids()[:20]:  # Limitar a primeros 20
            try:
                proc = psutil.Process(pid)
                processes.append(proc.name())
            except Exception as e:
                logger.warning(f"Error silencioso en environment_awareness.get_processes: {e}")
                # fallback: continuar
        return processes


# Singleton
_ura_environment_awareness: URAEnvironmentAwareness | None = None


def get_ura_environment_awareness() -> URAEnvironmentAwareness:
    """Obtener el singleton de conciencia del entorno de URA."""
    global _ura_environment_awareness
    if _ura_environment_awareness is None:
        _ura_environment_awareness = URAEnvironmentAwareness()
    return _ura_environment_awareness


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    env = get_ura_environment_awareness()

    print("Conciencia del entorno del sistema creada")
    print(env.get_environment_context())
