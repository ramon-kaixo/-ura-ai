#!/usr/bin/env python3
"""
URA - Registro y Verificación de Puertos con Auto-Redirección

Sistema para:
- Registrar qué aplicación usa cada puerto
- Detectar puertos ocupados
- Auto-redirigir a puertos alternativos cuando hay fallos
- Enviar alertas a mantenimiento
"""

import argparse
import json
import logging
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Importar port_assigner para búsqueda inteligente
try:
    from port_assigner import PortAssigner

    PORT_ASSIGNER_AVAILABLE = True
except ImportError:
    PORT_ASSIGNER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("PortAssigner no disponible, usando búsqueda simple")

logger = logging.getLogger(__name__)

# Ruta del archivo de configuración
CONFIG_PATH = Path(__file__).parent.parent / "config" / "port_registry.json"


@dataclass
class PortInfo:
    """Información sobre un puerto registrado"""

    port: int
    app: str
    status: str
    last_check: str
    auto_redirect_enabled: bool


@dataclass
class RedirectInfo:
    """Información sobre una redirección"""

    original_port: int
    new_port: int
    app: str
    timestamp: str
    reason: str


class PortRegistry:
    """Registro de puertos con auto-redirección"""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        self.redirects_log: list[RedirectInfo] = []

        # Inicializar PortAssigner si está disponible
        self.port_assigner = None
        if PORT_ASSIGNER_AVAILABLE:
            try:
                self.port_assigner = PortAssigner()
                logger.info("PortAssigner inicializado para búsqueda inteligente")
            except Exception as e:
                logger.warning(f"Error inicializando PortAssigner: {e}")

    def _load_config(self) -> dict:
        """Cargar configuración desde archivo"""
        try:
            with open(self.config_path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {self.config_path}")
            return self._default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando configuración: {e}")
            return self._default_config()

    def _default_config(self) -> dict:
        """Configuración por defecto"""
        return {
            "version": "1.0",
            "port_pool": {
                "ollama": {"primary": 11434, "backup": [11435, 11436, 11437, 11438, 11439]},
                "redis": {"primary": 6379, "backup": [6380, 6381, 6382, 6383]},
                "general": {"backup_range": [12000, 12999]},
            },
            "registered_ports": {},
            "alerts": {"enabled": True, "maintenance_alerts": True},
            "auto_redirect": {"enabled": True, "max_redirects": 3},
        }

    def _save_config(self) -> bool:
        """Guardar configuración en archivo"""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False

    def is_port_in_use(self, port: int) -> bool:
        """Verificar si un puerto está en uso"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("localhost", port))
                return result == 0
        except Exception as e:
            logger.debug(f"Error verificando puerto {port}: {e}")
            return False

    def get_process_using_port(self, port: int) -> str | None:
        """Obtener información del proceso que usa el puerto"""
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pid = result.stdout.strip().split("\n")[0]
                # Obtener nombre del proceso
                try:
                    ps_result = subprocess.run(
                        ["ps", "-p", pid, "-o", "comm="], capture_output=True, text=True, timeout=5
                    )
                    if ps_result.returncode == 0:
                        return f"{ps_result.stdout.strip()} (PID: {pid})"
                except Exception as e:
                    logger.warning(f"Error silencioso en port_registry.ps_lookup: {e}")
                    # fallback: continuar
                return f"PID: {pid}"
        except Exception as e:
            logger.debug(f"Error obteniendo proceso para puerto {port}: {e}")
        return None

    def register_port(self, app_name: str, port: int, auto_redirect: bool = True) -> bool:
        """Registrar un puerto para una aplicación"""
        self.config["registered_ports"][app_name] = {
            "port": port,
            "app": app_name,
            "status": "active",
            "last_check": datetime.now().isoformat(),
            "auto_redirect_enabled": auto_redirect,
        }
        return self._save_config()

    def list_ports(self) -> dict[str, PortInfo]:
        """Listar todos los puertos registrados"""
        result = {}
        for app_name, port_data in self.config["registered_ports"].items():
            result[app_name] = PortInfo(**port_data)
        return result

    def check_port(self, port: int) -> dict:
        """Verificar estado de un puerto específico"""
        in_use = self.is_port_in_use(port)
        process = self.get_process_using_port(port) if in_use else None

        return {
            "port": port,
            "in_use": in_use,
            "process": process,
            "timestamp": datetime.now().isoformat(),
        }

    def get_free_ports(self, count: int = 10) -> list[int]:
        """Obtener puertos libres"""
        free_ports = []

        # Primero verificar puertos de backup registrados
        for app_name, pool_data in self.config["port_pool"].items():
            if app_name == "general":
                continue
            if "backup" in pool_data:
                for port in pool_data["backup"]:
                    if not self.is_port_in_use(port):
                        free_ports.append(port)
                        if len(free_ports) >= count:
                            return free_ports

        # Si no hay suficientes, usar rango general
        if "general" in self.config["port_pool"]:
            range_start = self.config["port_pool"]["general"]["backup_range"][0]
            range_end = self.config["port_pool"]["general"]["backup_range"][1]
            for port in range(range_start, range_end):
                if not self.is_port_in_use(port):
                    free_ports.append(port)
                    if len(free_ports) >= count:
                        return free_ports

        return free_ports

    def find_alternative_port(self, app_name: str, current_port: int) -> int | None:
        """Encontrar puerto alternativo para una aplicación"""
        if not self.config["auto_redirect"]["enabled"]:
            logger.warning("Auto-redirección desactivada")
            return None

        # Usar PortAssigner para búsqueda inteligente si está disponible
        if self.port_assigner:
            try:
                best_port = self.port_assigner.find_best_port(current_port)
                if best_port and best_port != current_port:
                    logger.info(f"PortAssigner encontró mejor puerto: {best_port}")
                    return best_port
            except Exception as e:
                logger.warning(f"Error usando PortAssigner: {e}")

        # Fallback: buscar en pool específico de la aplicación
        if app_name in self.config["port_pool"]:
            pool_data = self.config["port_pool"][app_name]
            if "backup" in pool_data:
                for port in pool_data["backup"]:
                    if not self.is_port_in_use(port):
                        return port

        # Si no hay en pool específico, usar rango general
        if (
            "general" in self.config["port_pool"]
            and self.config["auto_redirect"]["fallback_to_general_pool"]
        ):
            free_ports = self.get_free_ports(count=1)
            if free_ports:
                return free_ports[0]

        return None

    def redirect_port(self, app_name: str, reason: str = "Port conflict") -> int | None:
        """Redirigir aplicación a puerto alternativo"""
        if app_name not in self.config["registered_ports"]:
            logger.error(f"Aplicación {app_name} no registrada")
            return None

        current_port = self.config["registered_ports"][app_name]["port"]
        auto_redirect = self.config["registered_ports"][app_name]["auto_redirect_enabled"]

        if not auto_redirect:
            logger.warning(f"Auto-redirección desactivada para {app_name}")
            return current_port

        # Verificar si el puerto actual está realmente ocupado
        if not self.is_port_in_use(current_port):
            logger.info(f"Puerto {current_port} no está ocupado, no se redirige")
            return current_port

        # Encontrar puerto alternativo (usando PortAssigner si está disponible)
        alternative_port = self.find_alternative_port(app_name, current_port)

        if alternative_port is None:
            logger.error(f"No se encontró puerto alternativo para {app_name}")
            # Reportar error al PortAssigner
            if self.port_assigner:
                self.port_assigner.report_port_error(current_port, reason)
            return None

        # Registrar redirección
        redirect_info = RedirectInfo(
            original_port=current_port,
            new_port=alternative_port,
            app=app_name,
            timestamp=datetime.now().isoformat(),
            reason=reason,
        )
        self.redirects_log.append(redirect_info)

        # Actualizar configuración
        self.config["registered_ports"][app_name]["port"] = alternative_port
        self.config["registered_ports"][app_name]["last_check"] = datetime.now().isoformat()
        self._save_config()

        # Reportar éxito al PortAssigner
        if self.port_assigner:
            self.port_assigner.report_port_success(alternative_port)

        # Enviar alerta a mantenimiento
        self._send_maintenance_alert(app_name, current_port, alternative_port, reason)

        logger.info(f"{app_name} redirigido de {current_port} a {alternative_port}")
        return alternative_port

    def _send_maintenance_alert(
        self, app_name: str, original_port: int, new_port: int, reason: str
    ):
        """Enviar alerta a mantenimiento"""
        if not self.config["alerts"]["enabled"] or not self.config["alerts"]["maintenance_alerts"]:
            return

        alert_msg = (
            f"🚨 ALERTA DE MANTENIMIENTO 🚨\n"
            f"Aplicación: {app_name}\n"
            f"Puerto original: {original_port}\n"
            f"Puerto nuevo: {new_port}\n"
            f"Razón: {reason}\n"
            f"Acción requerida: CAMBIAR CONFIGURACIÓN DE {app_name.upper()} PARA USAR PUERTO {new_port}\n"
            f"Timestamp: {datetime.now().isoformat()}"
        )

        logger.warning(alert_msg)

        # Aquí se podría integrar con Telegram u otros sistemas de alertas
        # Por ahora solo se logea

    def wake_service(self, app_name: str) -> bool:
        """Despertar servicio hibernado"""
        if app_name not in self.config["registered_ports"]:
            logger.error(f"Aplicación {app_name} no registrada")
            return False

        port = self.config["registered_ports"][app_name]["port"]

        # Implementación específica por aplicación
        if app_name.lower() == "ollama":
            try:
                subprocess.Popen(
                    ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                time.sleep(2)
                if self.is_port_in_use(port):
                    logger.info(f"Ollama despertado en puerto {port}")
                    return True
            except Exception as e:
                logger.error(f"Error despertando Ollama: {e}")

        logger.warning(f"No se puede despertar {app_name} automáticamente")
        return False

    def get_redirects_log(self) -> list[RedirectInfo]:
        """Obtener log de redirecciones"""
        return self.redirects_log


def main():
    """Punto de entrada CLI"""
    parser = argparse.ArgumentParser(description="URA - Registro de Puertos")
    parser.add_argument("--list", action="store_true", help="Listar todos los puertos")
    parser.add_argument("--check", type=int, metavar="PORT", help="Verificar puerto específico")
    parser.add_argument("--free", action="store_true", help="Mostrar puertos libres")
    parser.add_argument("--wake", type=str, metavar="APP", help="Despertar servicio")
    parser.add_argument("--redirect", type=str, metavar="APP", help="Redirigir aplicación")
    parser.add_argument("--register", nargs=2, metavar=("APP", "PORT"), help="Registrar puerto")
    parser.add_argument("--verbose", action="store_true", help="Modo verbose")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    registry = PortRegistry()

    if args.list:
        ports = registry.list_ports()
        print("\n=== PUERTOS REGISTRADOS ===")
        for app_name, port_info in ports.items():
            print(f"{app_name}: {port_info.port} ({port_info.status}) - {port_info.app}")
            print(f"  Auto-redirect: {port_info.auto_redirect_enabled}")
            print(f"  Last check: {port_info.last_check}")

    elif args.check:
        status = registry.check_port(args.check)
        print(f"\n=== PUERTO {args.check} ===")
        print(f"En uso: {status['in_use']}")
        if status["process"]:
            print(f"Proceso: {status['process']}")
        print(f"Timestamp: {status['timestamp']}")

    elif args.free:
        free_ports = registry.get_free_ports(count=10)
        print("\n=== PUERTOS LIBRES ===")
        print(f"Total: {len(free_ports)}")
        print(f"Puertos: {free_ports[:10]}")

    elif args.wake:
        success = registry.wake_service(args.wake)
        if success:
            print(f"✅ Servicio {args.wake} despertado")
        else:
            print(f"❌ No se pudo despertar {args.wake}")

    elif args.redirect:
        new_port = registry.redirect_port(args.redirect)
        if new_port:
            print(f"✅ {args.redirect} redirigido a puerto {new_port}")
        else:
            print(f"❌ No se pudo redirigir {args.redirect}")

    elif args.register:
        app_name, port = args.register
        success = registry.register_port(app_name, int(port))
        if success:
            print(f"✅ {app_name} registrado en puerto {port}")
        else:
            print(f"❌ Error registrando {app_name}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
