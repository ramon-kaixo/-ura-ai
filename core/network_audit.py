#!/usr/bin/env python3
"""
Sistema de Auditoría de Red - URA
Escaneo de puertos, health check de APIs y gestión de IPs/Puertos
"""

import json
import logging
import socket
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


@dataclass
class PortInfo:
    """Información de un puerto"""

    port: int
    protocol: str
    process_name: str
    pid: int
    ip_address: str
    is_docker: bool
    container_name: str = ""
    api_endpoint: str = ""
    health_status: str = "unknown"
    is_authorized: bool = False
    status: str = "UNKNOWN"  # OCCUPIED, CONFLICT, FREE


@dataclass
class APIHealthCheck:
    """Resultado de health check de API"""

    endpoint: str
    port: int
    status: str
    response_time: float
    content_available: bool
    error: str = ""


class NetworkAuditSystem:
    """Sistema de Auditoría de Red"""

    # Tabla de Asignación Fija
    FIXED_ASSIGNMENTS = {
        "ollama": {"port": 11434, "ip": "127.0.0.1", "api_endpoint": "/api/tags"},
        "windsurf": {"port": 3000, "ip": "127.0.0.1", "api_endpoint": "/health"},
        "redis": {"port": 6379, "ip": "127.0.0.1", "api_endpoint": None},
        "postgres": {"port": 5432, "ip": "127.0.0.1", "api_endpoint": None},
        "n8n": {"port": 5678, "ip": "127.0.0.1", "api_endpoint": "/healthz"},
    }

    # Bandeja de reserva (5 puertos alternativos)
    RESERVE_PORTS = [11436, 11437, 11438, 11439, 11440]

    # Lista maestra de puertos permitidos (autorizados)
    ALLOWED_PORTS = {
        11434: {"service": "ollama", "expected_content": "models"},
        3000: {"service": "windsurf", "expected_content": None},
        6379: {"service": "redis", "expected_content": None},
        5432: {"service": "postgres", "expected_content": None},
        80: {"service": "http", "expected_content": None},
        443: {"service": "https", "expected_content": None},
        8000: {"service": "http_alt", "expected_content": None},
        8888: {"service": "jupyter", "expected_content": None},
        9090: {"service": "prometheus", "expected_content": None},
    }

    # APIs conocidas para health check
    KNOWN_APIS = {
        11434: {"name": "ollama", "endpoint": "/api/tags", "expected_content": "models"},
        3000: {"name": "windsurf", "endpoint": "/health", "expected_content": None},
    }

    def __init__(self, use_localhost: bool = True, local_ip: str | None = None):
        """
        Inicializar sistema de auditoría

        Args:
            use_localhost: Usar 127.0.0.1 por seguridad
            local_ip: IP local de la Mac M4 (opcional)
        """
        self.use_localhost = use_localhost
        self.local_ip = local_ip or self._get_local_ip()
        self.inventory: dict[str, PortInfo] = {}
        self.api_health: dict[str, APIHealthCheck] = {}
        self.audit_log: list[dict] = []
        self.inventory_file = Path(__file__).parent.parent / "config" / "network_inventory.json"
        self.allowed_ports_file = Path(__file__).parent.parent / "config" / "allowed_ports.json"
        self.conflict_log_file = Path(__file__).parent.parent / "logs" / "alerta_conflicto.log"

        # Cargar configuración de puertos permitidos
        self._load_allowed_ports()

        # Cargar inventario existente
        self._load_inventory()

    def _load_allowed_ports(self):
        """Cargar puertos permitidos desde archivo de configuración"""
        try:
            if self.allowed_ports_file.exists():
                with open(self.allowed_ports_file) as f:
                    config = json.load(f)
                    self.ALLOWED_PORTS = dict(config.get("port_info", {}).items())
                    self.RESERVE_PORTS = config.get(
                        "reserve_ports", [11436, 11437, 11438, 11439, 11440]
                    )
                    logger.info(f"Puertos permitidos cargados desde {self.allowed_ports_file}")
            else:
                # Usar valores por defecto si no existe el archivo
                self.ALLOWED_PORTS = {
                    11434: {"service": "ollama", "expected_content": "models"},
                    3000: {"service": "windsurf", "expected_content": None},
                    6379: {"service": "redis", "expected_content": None},
                    5432: {"service": "postgres", "expected_content": None},
                    80: {"service": "http", "expected_content": None},
                    443: {"service": "https", "expected_content": None},
                    8000: {"service": "http_alt", "expected_content": None},
                    8888: {"service": "jupyter", "expected_content": None},
                    9090: {"service": "prometheus", "expected_content": None},
                }
                self.RESERVE_PORTS = [11436, 11437, 11438, 11439, 11440]
                logger.warning(
                    f"Archivo {self.allowed_ports_file} no encontrado, usando valores por defecto"
                )
        except Exception as e:
            logger.error(f"Error cargando puertos permitidos: {e}")
            # Usar valores por defecto en caso de error
            self.ALLOWED_PORTS = {
                11434: {"service": "ollama", "expected_content": "models"},
                3000: {"service": "windsurf", "expected_content": None},
                6379: {"service": "redis", "expected_content": None},
                5432: {"service": "postgres", "expected_content": None},
                80: {"service": "http", "expected_content": None},
                443: {"service": "https", "expected_content": None},
                8000: {"service": "http_alt", "expected_content": None},
                8888: {"service": "jupyter", "expected_content": None},
                9090: {"service": "prometheus", "expected_content": None},
            }
            self.RESERVE_PORTS = [11436, 11437, 11438, 11439, 11440]

    def _log_conflict_alert(self, port_info: PortInfo):
        """Registrar alerta de conflicto en tiempo real"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_message = f"[{timestamp}] ⚠️ CONFLICTO DE PUERTO: Puerto {port_info.port} ({port_info.process_name}, PID: {port_info.pid}) NO AUTORIZADO"

        # Mostrar en consola
        print(f"\n{alert_message}\n")

        # Guardar en archivo de log
        try:
            self.conflict_log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.conflict_log_file, "a") as f:
                f.write(alert_message + "\n")
            logger.warning(f"Alerta de conflicto registrada para puerto {port_info.port}")
        except Exception as e:
            logger.error(f"Error guardando alerta de conflicto: {e}")

    def _get_local_ip(self) -> str:
        """Obtener IP local de la Mac M4"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"

    def _load_inventory(self):
        """Cargar inventario desde JSON"""
        try:
            if self.inventory_file.exists():
                with open(self.inventory_file) as f:
                    data = json.load(f)
                    self.inventory = {
                        k: PortInfo(**v) for k, v in data.get("inventory", {}).items()
                    }
                    self.api_health = {
                        k: APIHealthCheck(**v) for k, v in data.get("api_health", {}).items()
                    }
                    self.audit_log = data.get("audit_log", [])
                logger.info(f"Inventario cargado: {len(self.inventory)} puertos")
        except Exception as e:
            logger.error(f"Error cargando inventario: {e}")

    def _save_inventory(self):
        """Guardar inventario en JSON"""
        try:
            self.inventory_file.parent.mkdir(exist_ok=True)
            data = {
                "inventory": {k: asdict(v) for k, v in self.inventory.items()},
                "api_health": {k: asdict(v) for k, v in self.api_health.items()},
                "audit_log": self.audit_log[-100:],  # Guardar últimos 100 logs
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.inventory_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Inventario guardado: {len(self.inventory)} puertos")
        except Exception as e:
            logger.error(f"Error guardando inventario: {e}")

    def scan_ports(self) -> dict[str, PortInfo]:
        """
        Escanear todos los puertos (nativos y Docker)
        Usa lsof y netstat
        """
        logger.info("Escaneando puertos...")
        self.inventory = {}

        # Escanear con lsof
        self._scan_with_lsof()

        # Escanear con netstat (complementario)
        self._scan_with_netstat()

        # Escanear contenedores de Docker
        self._scan_docker_containers()

        # Validar puertos (autorizados vs no autorizados)
        self._validate_ports()

        # Guardar inventario
        self._save_inventory()

        logger.info(f"Escaneo completado: {len(self.inventory)} puertos encontrados")
        return self.inventory

    def _scan_with_lsof(self) -> None:
        """Escanear puertos usando lsof"""
        try:
            result = subprocess.run(
                ["lsof", "-i", "-P", "-n"], capture_output=True, text=True, timeout=30
            )

            for line in result.stdout.split("\n")[1:]:  # Saltar header
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) < 8:
                    continue

                try:
                    command = parts[0]
                    pid = int(parts[1])
                    protocol = parts[4]
                    address = parts[7]

                    # Extraer puerto y dirección IP
                    if ":" in address:
                        ip_address, port_str = address.rsplit(":", 1)
                        port = int(port_str)
                    else:
                        continue

                    key = f"{protocol}_{port}"
                    self.inventory[key] = PortInfo(
                        port=port,
                        protocol=protocol,
                        process_name=command,
                        pid=pid,
                        ip_address=ip_address,
                        is_docker=False,
                        container_name="",
                    )

                except (ValueError, IndexError):
                    continue

        except subprocess.TimeoutExpired:
            logger.warning("lsof timeout")
        except FileNotFoundError:
            logger.warning("lsof no encontrado, usando netstat")
        except Exception as e:
            logger.error(f"Error escaneando con lsof: {e}")

    def _scan_with_netstat(self) -> None:
        """Escanear puertos usando netstat (complementario)"""
        try:
            result = subprocess.run(["netstat", "-an"], capture_output=True, text=True, timeout=30)

            for line in result.stdout.split("\n"):
                if "LISTEN" not in line or "tcp" not in line.lower():
                    continue

                try:
                    parts = line.split()
                    address = parts[3] if len(parts) > 3 else ""

                    if ":" in address:
                        ip_address, port_str = address.rsplit(":", 1)
                        port = int(port_str)

                        # Verificar si ya existe en inventario
                        key = f"tcp_{port}"
                        if key not in self.inventory:
                            self.inventory[key] = PortInfo(
                                port=port,
                                protocol="tcp",
                                process_name="unknown",
                                pid=0,
                                ip_address=ip_address,
                                is_docker=False,
                                container_name="",
                            )

                except (ValueError, IndexError):
                    continue

        except subprocess.TimeoutExpired:
            logger.warning("netstat timeout")
        except FileNotFoundError:
            logger.warning("netstat no encontrado")
        except Exception as e:
            logger.error(f"Error escaneando con netstat: {e}")

    def _scan_docker_containers(self) -> None:
        """Escanear contenedores de Docker y sus puertos"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            for line in result.stdout.split("\n"):
                if not line.strip():
                    continue

                try:
                    parts = line.split("\t")
                    if len(parts) < 2:
                        continue

                    container_name = parts[0]
                    ports_info = parts[1]

                    # Verificar si usa puertos dinámicos (sin mapeo fijo)
                    has_dynamic_port = False
                    for port_mapping in ports_info.split(","):
                        if "->" not in port_mapping and "0.0.0.0:" in port_mapping:
                            has_dynamic_port = True
                            logger.warning(
                                f"Contenedor {container_name} usa puerto dinámico: {port_mapping}"
                            )

                    if has_dynamic_port:
                        logger.error(f"CONTENEDOR CON PUERTO DINÁMICO PROHIBIDO: {container_name}")
                        self.audit_log.append(
                            {
                                "timestamp": datetime.now().isoformat(),
                                "action": "dynamic_port_detected",
                                "container": container_name,
                                "ports": ports_info,
                                "severity": "CRITICAL",
                            }
                        )

                    # Extraer puertos mapeados
                    for port_mapping in ports_info.split(","):
                        if "->" in port_mapping:
                            try:
                                host_port = int(port_mapping.split(":")[1].split("->")[0])
                                key = f"docker_{host_port}"

                                # Actualizar si ya existe
                                if key in self.inventory:
                                    self.inventory[key].is_docker = True
                                    self.inventory[key].container_name = container_name
                                else:
                                    self.inventory[key] = PortInfo(
                                        port=host_port,
                                        protocol="tcp",
                                        process_name="docker",
                                        pid=0,
                                        ip_address="127.0.0.1",
                                        is_docker=True,
                                        container_name=container_name,
                                    )
                            except (ValueError, IndexError):
                                continue

                except Exception as e:
                    logger.warning(f"Error procesando línea de docker: {e}")

        except subprocess.TimeoutExpired:
            logger.warning("docker ps timeout")
        except FileNotFoundError:
            logger.warning("docker no encontrado")
        except Exception as e:
            logger.error(f"Error escaneando contenedores Docker: {e}")

    def _validate_ports(self) -> None:
        """Validar puertos y marcar como OCCUPIED/CONFLICT/FREE"""
        for _key, port_info in self.inventory.items():
            # Verificar si está en lista de permitidos
            if port_info.port in self.ALLOWED_PORTS:
                port_info.is_authorized = True
                port_info.status = "OCCUPIED"
                logger.debug(f"Puerto {port_info.port} autorizado: {port_info.process_name}")
            else:
                port_info.is_authorized = False
                port_info.status = "CONFLICT"
                logger.warning(f"Puerto {port_info.port} NO autorizado: {port_info.process_name}")

                # Registrar en log
                self.audit_log.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "action": "unauthorized_port",
                        "port": port_info.port,
                        "process": port_info.process_name,
                        "pid": port_info.pid,
                        "severity": "WARNING",
                    }
                )

    def validate_port_identity(self, port: int, expected_content: str | None = None) -> bool:
        """
        Validar identidad de puerto (validación de contenido)
        Si responde algo distinto a lo esperado, marcar como CONFLICTO

        Args:
            port: Puerto a validar
            expected_content: Contenido esperado en la respuesta

        Returns:
            bool: True si la identidad es válida, False si hay conflicto
        """
        if port not in self.KNOWN_APIS:
            return True  # No es una API conocida, no se valida

        api_info = self.KNOWN_APIS[port]
        expected_content = expected_content or api_info.get("expected_content")

        try:
            ip = self.local_ip if not self.use_localhost else "127.0.0.1"
            url = f"http://{ip}:{port}{api_info['endpoint']}"

            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                content = response.text

                # Verificar contenido esperado
                if expected_content:
                    if expected_content in content:
                        logger.info(
                            f"Puerto {port} identidad válida: contiene '{expected_content}'"
                        )
                        return True
                    else:
                        logger.error(f"Puerto {port} CONFLICTO: no contiene '{expected_content}'")
                        self._mark_port_as_conflict(
                            port, f"Expected '{expected_content}' not found"
                        )
                        return False
                else:
                    logger.info(f"Puerto {port} identidad válida: responde HTTP 200")
                    return True
            else:
                logger.error(f"Puerto {port} CONFLICTO: responde HTTP {response.status_code}")
                self._mark_port_as_conflict(port, f"HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Puerto {port} CONFLICTO: {str(e)}")
            self._mark_port_as_conflict(port, str(e))
            return False

    def _mark_port_as_conflict(self, port: int, reason: str) -> None:
        """Marcar puerto como CONFLICTO y registrar en log"""
        key = f"tcp_{port}"
        if key in self.inventory:
            self.inventory[key].status = "CONFLICT"
            self.inventory[key].is_authorized = False

            # Enviar alerta en tiempo real
            self._log_conflict_alert(self.inventory[key])

        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "port_conflict",
                "port": port,
                "reason": reason,
                "severity": "CRITICAL",
            }
        )

        # Guardar inventario
        self._save_inventory()

    def move_service_to_reserve(self, service_name: str, current_port: int) -> int | None:
        """
        Mover servicio a puerto de reserva si hay conflicto

        Args:
            service_name: Nombre del servicio
            current_port: Puerto actual

        Returns:
            int: Nuevo puerto asignado o None si no hay puertos disponibles
        """
        logger.info(f"Intentando mover {service_name} a puerto de reserva (actual: {current_port})")

        # Obtener puerto disponible
        new_port = self.get_available_port()
        if new_port:
            logger.info(f"Moviendo {service_name} de puerto {current_port} a {new_port}")

            # Actualizar tabla de asignación fija
            if service_name in self.FIXED_ASSIGNMENTS:
                self.FIXED_ASSIGNMENTS[service_name]["port"] = new_port

            # Actualizar lista de permitidos
            if current_port in self.ALLOWED_PORTS:
                del self.ALLOWED_PORTS[current_port]
            self.ALLOWED_PORTS[new_port] = self.ALLOWED_PORTS.get(
                current_port, {"service": service_name, "expected_content": None}
            )

            # Registrar en log
            self.audit_log.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "move_to_reserve",
                    "service": service_name,
                    "old_port": current_port,
                    "new_port": new_port,
                    "reason": "Port conflict detected",
                }
            )

            # Guardar inventario
            self._save_inventory()

            return new_port
        else:
            logger.error("No hay puertos de reserva disponibles")
            return None

    def health_check_apis(self) -> dict[str, APIHealthCheck]:
        """
        Health check de APIs conocidas
        Verifica que responden contenido y no están vacías
        También valida identidad de puertos
        """
        logger.info("Realizando health check de APIs...")
        self.api_health = {}

        for port, api_info in self.KNOWN_APIS.items():
            key = f"{api_info['name']}_{port}"

            try:
                ip = self.local_ip if not self.use_localhost else "127.0.0.1"
                url = f"http://{ip}:{port}{api_info['endpoint']}"

                start_time = datetime.now()
                response = requests.get(url, timeout=5)
                end_time = datetime.now()

                response_time = (end_time - start_time).total_seconds()

                if response.status_code == 200:
                    content = response.text

                    # Verificar si hay contenido esperado
                    content_available = True
                    if api_info["expected_content"]:
                        content_available = api_info["expected_content"] in content

                    # Verificar si no está vacío
                    if not content or content == "{}" or content == "[]":
                        content_available = False

                    # Validar identidad del puerto
                    identity_valid = self.validate_port_identity(port, api_info["expected_content"])

                    self.api_health[key] = APIHealthCheck(
                        endpoint=url,
                        port=port,
                        status="healthy" if content_available and identity_valid else "conflict",
                        response_time=response_time,
                        content_available=content_available,
                        error="" if identity_valid else "Identity validation failed",
                    )

                    logger.info(f"API {api_info['name']}:{port} - {self.api_health[key].status}")
                else:
                    self.api_health[key] = APIHealthCheck(
                        endpoint=url,
                        port=port,
                        status="error",
                        response_time=response_time,
                        content_available=False,
                        error=f"HTTP {response.status_code}",
                    )

            except requests.exceptions.Timeout:
                self.api_health[key] = APIHealthCheck(
                    endpoint=f"http://{ip}:{port}{api_info['endpoint']}",
                    port=port,
                    status="timeout",
                    response_time=5.0,
                    content_available=False,
                    error="Timeout",
                )
            except Exception as e:
                self.api_health[key] = APIHealthCheck(
                    endpoint=f"http://{ip}:{port}{api_info['endpoint']}",
                    port=port,
                    status="error",
                    response_time=0.0,
                    content_available=False,
                    error=str(e),
                )

        # Guardar inventario
        self._save_inventory()

        logger.info(f"Health check completado: {len(self.api_health)} APIs verificadas")
        return self.api_health

    def get_available_port(self) -> int | None:
        """
        Obtener un puerto disponible de la bandeja de reserva
        Reasigna automáticamente si el puerto necesario está ocupado
        """
        for port in self.RESERVE_PORTS:
            key = f"tcp_{port}"
            if key not in self.inventory:
                logger.info(f"Puerto disponible encontrado: {port}")
                return port
            else:
                logger.warning(f"Puerto {port} está ocupado por {self.inventory[key].process_name}")

        logger.error("No hay puertos disponibles en la bandeja de reserva")
        return None

    def reassign_port(self, service_name: str, current_port: int) -> int | None:
        """
        Reasignar puerto para un servicio si está ocupado
        Usa un puerto de la bandeja de reserva
        """
        logger.info(f"Intentando reasignar puerto para {service_name} (actual: {current_port})")

        # Verificar si el puerto actual está ocupado por otro proceso
        key = f"tcp_{current_port}"
        if key in self.inventory:
            logger.warning(
                f"Puerto {current_port} está ocupado por {self.inventory[key].process_name}"
            )

            # Obtener puerto disponible
            new_port = self.get_available_port()
            if new_port:
                logger.info(f"Reasignando {service_name} de puerto {current_port} a {new_port}")

                # Actualizar tabla de asignación fija
                if service_name in self.FIXED_ASSIGNMENTS:
                    self.FIXED_ASSIGNMENTS[service_name]["port"] = new_port

                # Registrar en log
                self.audit_log.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "action": "reassign_port",
                        "service": service_name,
                        "old_port": current_port,
                        "new_port": new_port,
                        "reason": f"Port occupied by {self.inventory[key].process_name}",
                    }
                )

                # Guardar inventario
                self._save_inventory()

                return new_port
        else:
            logger.info(f"Puerto {current_port} está disponible, no necesita reasignación")
            return current_port

        return None

    def get_audit_report(self) -> dict:
        """
        Generar reporte de auditoría
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "total_ports": len(self.inventory),
            "docker_ports": sum(1 for p in self.inventory.values() if p.is_docker),
            "native_ports": sum(1 for p in self.inventory.values() if not p.is_docker),
            "api_health": {
                "healthy": sum(1 for h in self.api_health.values() if h.status == "healthy"),
                "empty": sum(1 for h in self.api_health.values() if h.status == "empty"),
                "error": sum(
                    1 for h in self.api_health.values() if h.status in ["error", "timeout"]
                ),
            },
            "fixed_assignments": self.FIXED_ASSIGNMENTS,
            "reserve_ports": self.RESERVE_PORTS,
            "use_localhost": self.use_localhost,
            "local_ip": self.local_ip,
        }

    def run_full_audit(self) -> dict:
        """
        Ejecutar auditoría completa
        Escaneo de puertos + health check de APIs
        """
        logger.info("Iniciando auditoría completa de red...")

        # Escanear puertos
        self.scan_ports()

        # Health check de APIs
        self.health_check_apis()

        # Generar reporte
        report = self.get_audit_report()

        # Registrar en log
        self.audit_log.append(
            {"timestamp": datetime.now().isoformat(), "action": "full_audit", "report": report}
        )

        # Guardar inventario
        self._save_inventory()

        logger.info(
            f"Auditoría completada: {report['total_ports']} puertos, {report['api_health']['healthy']} APIs healthy"
        )
        return report


# Instancia global del sistema de auditoría
network_audit = NetworkAuditSystem(use_localhost=True)


if __name__ == "__main__":
    # Prueba del sistema de auditoría
    audit = NetworkAuditSystem(use_localhost=True)

    print("=== Sistema de Auditoría de Red ===")
    print(f"Usando: {'localhost' if audit.use_localhost else audit.local_ip}")
    print(f"IP local: {audit.local_ip}")
    print()

    # Ejecutar auditoría completa
    report = audit.run_full_audit()

    print("\n=== Reporte de Auditoría ===")
    print(f"Puertos totales: {report['total_ports']}")
    print(f"Puertos Docker: {report['docker_ports']}")
    print(f"Puertos nativos: {report['native_ports']}")
    print(f"APIs healthy: {report['api_health']['healthy']}")
    print(f"APIs vacías: {report['api_health']['empty']}")
    print(f"APIs con error: {report['api_health']['error']}")
    print()

    print("=== Puertos en uso ===")
    for _key, port_info in audit.inventory.items():
        print(
            f"{port_info.port}: {port_info.process_name} (PID: {port_info.pid}) - Docker: {port_info.is_docker}"
        )

    print("\n=== Health Check de APIs ===")
    for _key, health in audit.api_health.items():
        print(f"{health.endpoint}: {health.status} ({health.response_time:.3f}s)")
