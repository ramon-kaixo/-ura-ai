#!/usr/bin/env python3
"""
core/port_manager.py - Gestor de Puertos para Evitar Conflictos
Centraliza la gestión de puertos para evitar conflictos entre aplicaciones
"""

import json
import logging
import socket
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class PortManager:
    """Gestor centralizado de puertos"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or str(
            Path(__file__).parent.parent / "config" / "ports_config.json"
        )
        self.config = self._load_config()
        self.assigned_ports = {}
        self.port_usage_history = {}
        self._load_port_history()

    def _load_port_history(self):
        """Cargar historial de uso de puertos"""
        try:
            history_file = Path(self.config_path).parent.parent / "data" / "port_history.json"
            if history_file.exists():
                with open(history_file) as f:
                    self.port_usage_history = json.load(f)
        except Exception as e:
            logger.warning(f"Error loading port history: {e}")
            self.port_usage_history = {}

    def _save_port_history(self):
        """Guardar historial de uso de puertos"""
        try:
            history_file = Path(self.config_path).parent.parent / "data" / "port_history.json"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(history_file, "w") as f:
                json.dump(self.port_usage_history, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving port history: {e}")

    def _record_port_usage(self, service_name: str, port: int):
        """Registrar uso de puerto"""
        self.port_usage_history[service_name] = {
            "port": port,
            "last_used": datetime.now().isoformat(),
            "count": self.port_usage_history.get(service_name, {}).get("count", 0) + 1,
        }
        self._save_port_history()

    def _load_config(self) -> dict:
        """Cargar configuración de puertos"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file) as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file not found: {self.config_path}")
                return self._default_config()
        except Exception as e:
            logger.error(f"Error loading port config: {e}")
            return self._default_config()

    def _default_config(self) -> dict:
        """Configuración por defecto"""
        return {
            "port_manager": {
                "enabled": True,
                "auto_assign": True,
                "port_range": {"start": 5000, "end": 5999},
                "reserved_ports": {
                    "ura_api": 5000,
                    "ura_api_v2": 5001,
                    "ura_api_auto_repair": 5002,
                    "ura_dashboard_web": 5003,
                    "prometheus": 9090,
                    "prometheus_metrics": 9091,
                    "grafana": 3000,
                    "ollama": 11434,
                    "redis": 6379,
                },
                "check_on_startup": True,
                "conflict_resolution": "skip",
            }
        }

    def is_port_available(self, port: int) -> bool:
        """Verificar si un puerto está disponible"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("localhost", port))
                return result != 0
        except Exception as e:
            logger.warning(f"Error checking port {port}: {e}")
            return False

    def get_port_for_service(self, service_name: str) -> int:
        """Obtener puerto para un servicio específico"""
        port_config = self.config.get("port_manager", {})
        reserved_ports = port_config.get("reserved_ports", {})

        if service_name in reserved_ports:
            port = reserved_ports[service_name]

            if self.is_port_available(port):
                self.assigned_ports[service_name] = port
                self._record_port_usage(service_name, port)
                logger.info(f"Port {port} assigned to {service_name}")
                return port
            else:
                return self._resolve_conflict(service_name, port)

        if port_config.get("auto_assign", True):
            return self._assign_available_port(service_name)

        raise ValueError(f"No port configured for service: {service_name}")

    def get_port_for_service_with_fallback(
        self, service_name: str, fallback_port: int | None = None
    ) -> int:
        """Obtener puerto con fallback si falla"""
        try:
            return self.get_port_for_service(service_name)
        except Exception:
            if fallback_port:
                logger.warning(f"Using fallback port {fallback_port} for {service_name}")
                self.assigned_ports[service_name] = fallback_port
                self._record_port_usage(service_name, fallback_port)
                return fallback_port
            raise

    def _resolve_conflict(self, service_name: str, port: int) -> int:
        """Resolver conflicto de puerto"""
        resolution = self.config.get("port_manager", {}).get("conflict_resolution", "skip")

        if resolution == "skip":
            logger.warning(f"Port {port} occupied for {service_name}, skipping")
            return port
        elif resolution == "kill":
            self._kill_process_on_port(port)
            return port
        elif resolution == "assign_new":
            return self._assign_available_port(service_name)
        else:
            return port

    def _kill_process_on_port(self, port: int) -> bool:
        """Matar proceso usando el puerto"""
        try:
            result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)

            if result.returncode == 0 and result.stdout.strip():
                pid = result.stdout.strip()
                subprocess.run(["kill", "-9", pid], capture_output=True)
                logger.info(f"Killed process {pid} on port {port}")
                return True
            else:
                logger.warning(f"No process found on port {port}")
                return False
        except Exception as e:
            logger.error(f"Error killing process on port {port}: {e}")
            return False

    def _assign_available_port(self, service_name: str) -> int:
        """Asignar puerto disponible automáticamente"""
        port_range = self.config.get("port_manager", {}).get("port_range", {})
        start = port_range.get("start", 5000)
        end = port_range.get("end", 5999)

        if service_name in self.port_usage_history:
            historical_port = self.port_usage_history[service_name].get("port")
            if historical_port and self.is_port_available(historical_port):
                self.assigned_ports[service_name] = historical_port
                self._record_port_usage(service_name, historical_port)
                logger.info(f"Reusing historical port {historical_port} for {service_name}")
                return historical_port

        for port in range(start, end):
            if self.is_port_available(port):
                self.assigned_ports[service_name] = port
                self._record_port_usage(service_name, port)
                logger.info(f"Auto-assigned port {port} to {service_name}")
                return port

        raise RuntimeError(f"No available ports in range {start}-{end}")

    def detect_all_conflicts(self) -> dict[str, dict]:
        """Detectar todos los conflictos de puertos"""
        conflicts = {}
        reserved_ports = self.config.get("port_manager", {}).get("reserved_ports", {})

        for service, port in reserved_ports.items():
            if not self.is_port_available(port):
                conflicts[service] = {
                    "port": port,
                    "status": "occupied",
                    "process": self._get_process_on_port(port),
                }

        return conflicts

    def _get_process_on_port(self, port: int) -> str | None:
        """Obtener información del proceso usando el puerto"""
        try:
            result = subprocess.run(["lsof", "-i", f":{port}"], capture_output=True, text=True)

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    return lines[1]
            return None
        except Exception as e:
            logger.warning(f"Error getting process on port {port}: {e}")
            return None

    def get_port_statistics(self) -> dict:
        """Obtener estadísticas de uso de puertos"""
        total_assigned = len(self.assigned_ports)
        total_reserved = len(self.config.get("port_manager", {}).get("reserved_ports", {}))
        conflicts = self.detect_all_conflicts()

        return {
            "total_assigned": total_assigned,
            "total_reserved": total_reserved,
            "conflicts": len(conflicts),
            "assigned_ports": self.assigned_ports.copy(),
            "conflict_details": conflicts,
            "port_usage_history": self.port_usage_history.copy(),
        }

    def auto_resolve_all_conflicts(self):
        """Resolver automáticamente todos los conflictos"""
        conflicts = self.detect_all_conflicts()
        resolution = self.config.get("port_manager", {}).get("conflict_resolution", "skip")

        if resolution == "kill":
            for service, info in conflicts.items():
                port = info["port"]
                if self._kill_process_on_port(port):
                    logger.info(
                        f"Resolved conflict for {service} by killing process on port {port}"
                    )
        elif resolution == "assign_new":
            for service in conflicts:
                self._assign_available_port(service)
                logger.info(f"Resolved conflict for {service} by assigning new port")

        return len(conflicts)

    def check_all_reserved_ports(self) -> dict[str, bool]:
        """Verificar todos los puertos reservados"""
        reserved_ports = self.config.get("port_manager", {}).get("reserved_ports", {})
        status = {}

        for service, port in reserved_ports.items():
            status[service] = self.is_port_available(port)

        return status

    def get_assigned_ports(self) -> dict[str, int]:
        """Obtener todos los puertos asignados"""
        return self.assigned_ports.copy()

    def release_port(self, service_name: str):
        """Liberar puerto asignado a un servicio"""
        if service_name in self.assigned_ports:
            port = self.assigned_ports[service_name]
            del self.assigned_ports[service_name]
            logger.info(f"Released port {port} from {service_name}")


_port_manager_instance = None


def get_port_manager() -> PortManager:
    """Obtener instancia singleton del gestor de puertos"""
    global _port_manager_instance
    if _port_manager_instance is None:
        _port_manager_instance = PortManager()
    return _port_manager_instance


if __name__ == "__main__":
    manager = PortManager()

    print("Checking reserved ports:")
    status = manager.check_all_reserved_ports()
    for service, available in status.items():
        status_str = "Available" if available else "Occupied"
        print(f"  {service}: {status_str}")

    print("\nAssigned ports:")
    assigned = manager.get_assigned_ports()
    for service, port in assigned.items():
        print(f"  {service}: {port}")
