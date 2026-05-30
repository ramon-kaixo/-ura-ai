#!/usr/bin/env python3
"""
core/port_conflict_monitor.py - Monitor de Conflictos de Puertos en Tiempo Real
Detecta conflictos de puertos en tiempo real y alerta
"""

import logging
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class PortConflictMonitor:
    """Monitor de conflictos de puertos en tiempo real"""

    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.alert_callback: Callable | None = None
        self.last_conflicts = {}

    def set_alert_callback(self, callback: Callable[[dict], None]):
        """Establecer callback para alertas de conflictos"""
        self.alert_callback = callback

    def start(self):
        """Iniciar monitor de conflictos"""
        if self.running:
            logger.warning("Conflict monitor already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Port conflict monitor started")

    def stop(self):
        """Detener monitor de conflictos"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Port conflict monitor stopped")

    def _monitor_loop(self):
        """Loop de monitoreo"""
        from core.port_manager import get_port_manager

        port_manager = get_port_manager()

        while self.running:
            try:
                # Detectar conflictos actuales
                current_conflicts = port_manager.detect_all_conflicts()

                # Comparar con conflictos anteriores
                new_conflicts = self._detect_new_conflicts(current_conflicts)

                if new_conflicts and self.alert_callback:
                    self.alert_callback(new_conflicts)

                self.last_conflicts = current_conflicts

            except Exception as e:
                logger.error(f"Error in conflict monitor loop: {e}")

            time.sleep(self.check_interval)

    def _detect_new_conflicts(self, current_conflicts: dict) -> dict:
        """Detectar nuevos conflictos"""
        new_conflicts = {}

        for service, info in current_conflicts.items():
            if (
                service not in self.last_conflicts
                or self.last_conflicts[service]["process"] != info["process"]
            ):
                new_conflicts[service] = info

        return new_conflicts

    def check_now(self) -> dict:
        """Verificar conflictos ahora mismo"""
        from core.port_manager import get_port_manager

        port_manager = get_port_manager()
        return port_manager.detect_all_conflicts()

    def get_conflict_statistics(self) -> dict:
        """Obtener estadísticas de conflictos"""
        from core.port_manager import get_port_manager

        port_manager = get_port_manager()
        stats = port_manager.get_port_statistics()

        return {
            "total_conflicts": stats["conflicts"],
            "conflict_details": stats["conflict_details"],
            "monitoring": self.running,
            "check_interval": self.check_interval,
        }


# Singleton instance
_conflict_monitor_instance = None


def get_conflict_monitor(check_interval: int = 30) -> PortConflictMonitor:
    """Obtener instancia singleton del monitor de conflictos"""
    global _conflict_monitor_instance
    if _conflict_monitor_instance is None:
        _conflict_monitor_instance = PortConflictMonitor(check_interval)
    return _conflict_monitor_instance


if __name__ == "__main__":
    # Prueba del monitor de conflictos
    monitor = get_conflict_monitor(check_interval=5)

    def alert_callback(conflicts: dict):
        print(f"ALERT: New conflicts detected: {conflicts}")

    monitor.set_alert_callback(alert_callback)
    monitor.start()

    try:
        print("Monitoring for conflicts (press Ctrl+C to stop)...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("Monitoring stopped")
