#!/usr/bin/env python3
"""
Módulo: core/autonomous_maintenance.py
Propósito: Mantenimiento autónomo diario: escribe diario URA, rota logs, verifica espacio en disco.
Dependencias principales: datetime, psutil, URAdiary, ThreadCleaner, monitorear
Reglas especiales: Ventana de escritura diario entre 23:55-23:59. Nunca bloquear el bucle principal.
"""

import logging
import threading
import time
import datetime

from agents.agente_conectividad import AgenteConectividad
from agents.agente_red_telefonia import AgenteRedTelefonia
from core.disk_cleaner import limpiar
from core.disk_monitor import monitorear
from core.network_audit import NetworkAuditSystem
from core.thread_cleaner import ThreadCleaner

# Importar diario de URA
try:
    from core.ura_diary import URAdiary

    DIARY_AVAILABLE = True
except ImportError:
    DIARY_AVAILABLE = False

logger = logging.getLogger(__name__)


class AutonomousMaintenance:
    """Background daemon for autonomous system maintenance."""

    def __init__(self):
        self.activo = False
        self._thread = None
        self.audit = NetworkAuditSystem()
        self.cleaner = ThreadCleaner()
        self._agente_red = AgenteRedTelefonia()
        self._last_diary_date = None
        self._agente_conectividad = AgenteConectividad()

    def iniciar(self):
        """Arranca el ciclo de mantenimiento autónomo."""
        self.activo = True
        self._thread = threading.Thread(
            target=self._ciclo,
            daemon=True,
            name="AutonomousMaintenanceThread",
        )
        self._thread.start()
        logger.info("Mantenimiento autónomo iniciado")

    def detener(self):
        """Detiene el ciclo de mantenimiento."""
        self.activo = False

    def _ciclo(self):
        """Ciclo de mantenimiento cada 5 minutos."""
        while self.activo:
            try:
                # Escritura nocturna del diario a las 23:55
                if DIARY_AVAILABLE:
                    hora_actual = datetime.datetime.now()
                    today = hora_actual.date()
                    if (
                        hora_actual.hour == 23
                        and hora_actual.minute >= 55
                        and self._last_diary_date != today
                    ):
                        try:
                            URAdiary().escribir_entrada_diaria()
                            logger.info("Diario nocturno escrito a las 23:55")
                        except Exception as e:
                            logger.error(f"Error escribiendo diario nocturno: {e}")

                estado_disco = monitorear()
                if estado_disco["estado"] == "critical":
                    logger.critical("Disco crítico — limpiando automáticamente")
                    limpiar(modo="safe")

                self.audit.run_full_audit()

                self.cleaner.clean_all_zombies()

                # Monitoreo de red (WiFi + router)
                red = self._agente_red.monitorear()
                if red["estado"] != "ok":
                    logger.warning(f"Red: {red['estado']}")

                # Conectividad multi-IP (Cloudflare tunnel / VPS / ISP)
                conectividad = self._agente_conectividad.monitorear()
                if not conectividad["ok"]:
                    logger.critical(f"Sin conectividad: {conectividad.get('error')}")

            except Exception as e:
                logger.error(f"Error en mantenimiento autónomo: {e}")

            time.sleep(300)

    def estado(self) -> dict:
        """Estado actual del mantenimiento."""
        return {
            "activo": self.activo,
            "thread_vivo": self._thread.is_alive() if self._thread else False,
        }
