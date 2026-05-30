#!/usr/bin/env python3
"""
Service Manager — FASE 1.1
────────────────────────────
Gestiona el ciclo de vida de servicios externos:
Ollama, Docker, n8n, Grafana, PostgreSQL, Redis.
Patrón de estados: STOPPED → STARTING → RUNNING → DEGRADED.
"""

import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import psutil

from core.logging_config import get_logger

logger = get_logger("service_manager", log_dir="./logs")


class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class Service:
    """Definición de un servicio gestionado."""

    name: str
    port: int | None = None
    process_name: str | None = None
    start_command: str | None = None
    stop_command: str | None = None
    health_url: str | None = None
    health_timeout: int = 5
    restart_on_failure: bool = True
    max_restarts: int = 3

    # Estado interno
    status: ServiceStatus = ServiceStatus.STOPPED
    pid: int | None = None
    restart_count: int = 0
    last_check: float = 0


class ServiceManager:
    """
    Gestor de servicios externos de URA.

    Uso:
        sm = ServiceManager()
        sm.register(Service("ollama", port=11434))
        sm.start_all()
        sm.monitor()  # Bucle de health check
    """

    def __init__(self):
        self.services: dict[str, Service] = {}
        self.on_status_change: Callable | None = None

    def register(self, service: Service):
        """Registra un servicio para gestión."""
        self.services[service.name] = service
        logger.info(f"Servicio registrado: {service.name}")

    def start(self, name: str) -> bool:
        """Inicia un servicio por nombre."""
        svc = self.services.get(name)
        if not svc:
            logger.error(f"Servicio no encontrado: {name}")
            return False

        if svc.status == ServiceStatus.RUNNING:
            return True

        svc.status = ServiceStatus.STARTING
        self._notify(name)

        try:
            if svc.start_command:
                subprocess.Popen(
                    svc.start_command,
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(2)

            if self._health_check(svc):
                svc.status = ServiceStatus.RUNNING
                svc.restart_count = 0
                logger.info(f"✓ {name}: RUNNING (pid={svc.pid})")
            else:
                svc.status = ServiceStatus.DEGRADED
                logger.warning(f"⚠ {name}: DEGRADED (health check failed)")
                return False

        except Exception as e:
            svc.status = ServiceStatus.ERROR
            logger.error(f"✗ {name}: ERROR — {e}")
            return False

        self._notify(name)
        return svc.status == ServiceStatus.RUNNING

    def stop(self, name: str) -> bool:
        """Detiene un servicio."""
        svc = self.services.get(name)
        if not svc:
            return False

        try:
            if svc.stop_command:
                subprocess.run(svc.stop_command, shell=False, timeout=10)
            elif svc.pid:
                psutil.Process(svc.pid).terminate()
            svc.status = ServiceStatus.STOPPED
            svc.pid = None
            logger.info(f"✓ {name}: STOPPED")
        except Exception as e:
            logger.error(f"Error deteniendo {name}: {e}")
            return False

        self._notify(name)
        return True

    def start_all(self) -> dict[str, bool]:
        """Inicia todos los servicios registrados."""
        results = {}
        for name in self.services:
            results[name] = self.start(name)
        return results

    def stop_all(self):
        """Detiene todos los servicios."""
        for name in self.services:
            self.stop(name)

    def monitor(self, interval: int = 30):
        """Bucle de monitoreo continuo."""
        import time as _time

        while True:
            for name, svc in self.services.items():
                if svc.status == ServiceStatus.RUNNING:
                    if not self._health_check(svc):
                        svc.status = ServiceStatus.DEGRADED
                        self._notify(name)
                        if svc.restart_on_failure and svc.restart_count < svc.max_restarts:
                            logger.warning(f"Reiniciando {name} (intento {svc.restart_count + 1})")
                            svc.restart_count += 1
                            self.start(name)
            _time.sleep(interval)

    def _health_check(self, svc: Service) -> bool:
        """Verifica salud de un servicio."""
        now = time.time()
        if now - svc.last_check < 5:
            return svc.status == ServiceStatus.RUNNING
        svc.last_check = now

        # Check por puerto
        if svc.port:
            for conn in psutil.net_connections():
                if conn.laddr.port == svc.port and conn.status == "LISTEN":
                    svc.pid = conn.pid
                    return True

        # Check por nombre de proceso
        if svc.process_name:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if svc.process_name.lower() in proc.info["name"].lower():
                        svc.pid = proc.info["pid"]
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        # Check por URL
        if svc.health_url:
            try:
                import requests

                r = requests.get(svc.health_url, timeout=svc.health_timeout)
                return r.status_code == 200
            except Exception:
                return False

        return False

    def _notify(self, name: str):
        if self.on_status_change:
            svc = self.services[name]
            self.on_status_change(name, svc.status.value)

    def status_all(self) -> dict:
        """Devuelve el estado de todos los servicios."""
        return {name: svc.status.value for name, svc in self.services.items()}


# ── Instancia preconfigurada ──────────────────────────────


def create_default_manager() -> ServiceManager:
    """Crea un ServiceManager con los servicios estándar de URA."""
    sm = ServiceManager()

    sm.register(
        Service(
            name="ollama",
            port=11434,
            process_name="ollama",
            health_url="http://localhost:11434/api/tags",
            health_timeout=5,
        )
    )

    sm.register(
        Service(
            name="docker",
            process_name="docker",
            health_timeout=3,
        )
    )

    sm.register(
        Service(
            name="grafana",
            port=3000,
            health_url="http://localhost:3000/api/health",
            health_timeout=3,
        )
    )

    sm.register(
        Service(
            name="postgresql",
            port=5432,
            health_timeout=3,
        )
    )

    sm.register(
        Service(
            name="redis",
            port=6379,
            health_timeout=3,
        )
    )

    sm.register(
        Service(
            name="n8n",
            port=5678,
            health_url="http://localhost:5678/healthz",
            health_timeout=3,
        )
    )

    return sm


# ── Singleton ──────────────────────────────────────────────

_manager: ServiceManager | None = None


def get_service_manager() -> ServiceManager:
    global _manager
    if _manager is None:
        _manager = create_default_manager()
    return _manager
