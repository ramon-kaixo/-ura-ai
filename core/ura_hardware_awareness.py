#!/usr/bin/env python3
"""
Conciencia del Hardware y Sistema Operativo de URA - Nivel 23

URA tiene conocimiento de su hardware y sistema operativo:
- CPU, memoria, disco
- Sistema operativo y versión
- Capacidades del sistema
"""

import json
import logging
import platform
import psutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from core.ura_monitoring import get_ura_monitoring

logger = logging.getLogger(__name__)
monitor = get_ura_monitoring()

HARDWARE_AWARENESS_PATH = Path.home() / ".ura" / "hardware_awareness.json"
HARDWARE_AWARENESS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class HardwareInfo:
    """Información del hardware y sistema operativo."""

    scan_time: str
    os_name: str
    os_version: str
    cpu_cores: int
    cpu_freq: float
    total_memory_gb: float
    available_memory_gb: float
    disk_total_gb: float
    disk_free_gb: float
    python_version: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HardwareInfo":
        return cls(**data)


class URAHardwareAwareness:
    """Gestor de conciencia del hardware de URA."""

    def __init__(self):
        self.hardware_info = self._load_hardware_info()

    def _load_hardware_info(self) -> HardwareInfo:
        """Cargar información del hardware desde disco."""
        if HARDWARE_AWARENESS_PATH.exists():
            try:
                with open(HARDWARE_AWARENESS_PATH) as f:
                    data = json.load(f)
                    return HardwareInfo.from_dict(data)
            except Exception as e:
                logger.error(f"Error cargando información del hardware: {e}")

        return self._scan_hardware()

    def _scan_hardware(self) -> HardwareInfo:
        """Escanear hardware y sistema operativo con límites de performance."""
        import time

        start = time.time()

        try:
            # Información del sistema operativo
            os_name = platform.system()
            os_version = platform.release()

            # Información de CPU
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()

            # Información de memoria
            memory = psutil.virtual_memory()
            memory_total_gb = memory.total / (1024**3)
            memory_available_gb = memory.available / (1024**3)

            # Información de disco
            disk = psutil.disk_usage("/")
            disk_total_gb = disk.total / (1024**3)
            disk_free_gb = disk.free / (1024**3)

            duration = time.time() - start
            monitor.log_performance("hardware_awareness", "scan_hardware", duration)

            return HardwareInfo(
                scan_time=datetime.now().isoformat(),
                os_name=os_name,
                os_version=os_version,
                cpu_cores=cpu_count,
                cpu_freq=cpu_freq.current if cpu_freq else 0.0,
                total_memory_gb=memory_total_gb,
                available_memory_gb=memory_available_gb,
                disk_total_gb=disk_total_gb,
                disk_free_gb=disk_free_gb,
                python_version=platform.python_version(),
            )
        except Exception as e:
            monitor.log_error("hardware_awareness", "ScanError", str(e))
            raise

    def _save_hardware_info(self):
        """Guardar información del hardware a disco."""
        with open(HARDWARE_AWARENESS_PATH, "w") as f:
            json.dump(self.hardware_info.to_dict(), f, indent=2)

    def refresh_hardware_info(self):
        """Actualizar información del hardware."""
        self.hardware_info = self._scan_hardware()
        self._save_hardware_info()

    def get_hardware_context(self) -> str:
        """Genera contexto del hardware para el system prompt."""
        context_parts = ["CONCIENCIA DEL HARDWARE Y SISTEMA OPERATIVO:"]
        context_parts.append(
            f"- Sistema operativo: {self.hardware_info.os_name} {self.hardware_info.os_version}"
        )
        context_parts.append(
            f"- CPU: {self.hardware_info.cpu_cores} núcleos @ {self.hardware_info.cpu_freq:.0f} MHz"
        )
        context_parts.append(
            f"- Memoria: {self.hardware_info.available_memory_gb:.1f} GB disponibles de {self.hardware_info.total_memory_gb:.1f} GB"
        )
        context_parts.append(
            f"- Disco: {self.hardware_info.disk_free_gb:.1f} GB libres de {self.hardware_info.disk_total_gb:.1f} GB"
        )
        context_parts.append(f"- Python: {self.hardware_info.python_version}")

        return "\n".join(context_parts) + "\n"

    def get_system_capabilities(self) -> dict[str, str]:
        """Obtener capacidades del sistema."""
        return {
            "parallel_processing": str(self.hardware_info.cpu_cores > 4),
            "high_memory": str(self.hardware_info.total_memory_gb > 8),
            "gpu_available": "unknown",  # Se puede extender para detectar GPU
        }


# Singleton
_ura_hardware_awareness: URAHardwareAwareness | None = None


def get_ura_hardware_awareness() -> URAHardwareAwareness:
    """Obtener el singleton de conciencia del hardware de URA."""
    global _ura_hardware_awareness
    if _ura_hardware_awareness is None:
        _ura_hardware_awareness = URAHardwareAwareness()
    return _ura_hardware_awareness


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    hardware = get_ura_hardware_awareness()

    print("Conciencia del hardware y sistema operativo creada")
    print(hardware.get_hardware_context())
