#!/usr/bin/env python3
"""
URA - Gestor de Alertas y Errores

Sistema para:
- Detectar errores en tiempo real
- Enrutar a servicio de reparación
- Mantener bandeja de alertas
- Priorizar errores (críticos, medios, bajos)
- Modo silencioso vs verboso
"""

import argparse
import json
import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# Ruta del archivo de configuración
CONFIG_PATH = Path(__file__).parent.parent / "config" / "alert_manager.json"
ERROR_TAGS_PATH = Path(__file__).parent.parent / "config" / "error_tags.json"


class ErrorPriority(Enum):
    """Prioridad de errores"""

    CRITICAL = "critical"  # Reparación inmediata
    MEDIUM = "medium"  # Reparación en background
    LOW = "low"  # Reparación programada


class ErrorStatus(Enum):
    """Estado de errores"""

    DETECTED = "detected"
    ROUTING = "routing"
    REPAIRING = "repairing"
    TEMPORARILY_FIXED = "temporarily_fixed"
    SANDBOX = "sandbox"
    RESOLVED = "resolved"
    FAILED = "failed"


@dataclass
class Alert:
    """Alerta de error"""

    id: str
    source: str
    error_type: str
    message: str
    priority: ErrorPriority
    status: ErrorStatus
    timestamp: str
    context: dict
    repair_attempts: int = 0
    fix_tag: str | None = None


class AlertManager:
    """Gestor de alertas y errores"""

    def __init__(self, config_path: Path | None = None, silent_mode: bool = True):
        self.config_path = config_path or CONFIG_PATH
        self.error_tags_path = ERROR_TAGS_PATH
        self.config = self._load_config()
        self.error_tags = self._load_error_tags()
        self.silent_mode = silent_mode

        # Cola de alertas
        self.alert_queue = queue.Queue()
        self.active_alerts: dict[str, Alert] = {}

        # Callbacks para enrutamiento
        self.repair_callback: Callable | None = None
        self.sandbox_callback: Callable | None = None

        # Hilo de procesamiento
        self.processing_thread = None
        self.running = False

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
            "silent_mode": True,
            "max_repair_attempts": 3,
            "critical_timeout_seconds": 30,
            "medium_timeout_seconds": 300,
            "low_timeout_seconds": 3600,
            "auto_repair_enabled": True,
            "sandbox_enabled": True,
        }

    def _load_error_tags(self) -> dict:
        """Cargar etiquetas de errores"""
        try:
            with open(self.error_tags_path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de etiquetas no encontrado: {self.error_tags_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando etiquetas: {e}")
            return {}

    def _save_error_tags(self) -> bool:
        """Guardar etiquetas en archivo"""
        try:
            with open(self.error_tags_path, "w") as f:
                json.dump(self.error_tags, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando etiquetas: {e}")
            return False

    def set_repair_callback(self, callback: Callable):
        """Establecer callback para reparación"""
        self.repair_callback = callback

    def set_sandbox_callback(self, callback: Callable):
        """Establecer callback para sandbox"""
        self.sandbox_callback = callback

    def start(self):
        """Iniciar procesamiento de alertas"""
        if self.running:
            return

        self.running = True
        self.processing_thread = threading.Thread(target=self._process_alerts, daemon=True)
        self.processing_thread.start()
        logger.info(
            "AlertManager iniciado (modo silencioso)"
            if self.silent_mode
            else "AlertManager iniciado (modo verboso)"
        )

    def stop(self):
        """Detener procesamiento de alertas"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        logger.info("AlertManager detenido")

    def _process_alerts(self):
        """Procesar alertas en background"""
        while self.running:
            try:
                alert = self.alert_queue.get(timeout=1)
                self._route_alert(alert)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error procesando alerta: {e}")

    def _route_alert(self, alert: Alert):
        """Enrutar alerta al sistema apropiado"""
        if not self.silent_mode:
            logger.info(f"Enrutando alerta {alert.id}: {alert.error_type}")

        alert.status = ErrorStatus.ROUTING
        self.active_alerts[alert.id] = alert

        # Determinar acción basado en prioridad y estado
        if alert.priority == ErrorPriority.CRITICAL:
            self._handle_critical(alert)
        elif alert.priority == ErrorPriority.MEDIUM:
            self._handle_medium(alert)
        else:
            self._handle_low(alert)

    def _handle_critical(self, alert: Alert):
        """Manejar errores críticos"""
        if self.config["auto_repair_enabled"] and self.repair_callback:
            try:
                alert.status = ErrorStatus.REPAIRING
                success = self.repair_callback(alert)

                if success:
                    alert.status = ErrorStatus.TEMPORARILY_FIXED
                    alert.fix_tag = self._generate_fix_tag(alert)
                    self._save_error_tags()

                    if not self.silent_mode:
                        logger.info(f"Alerta {alert.id} solucionada temporalmente")
                else:
                    alert.repair_attempts += 1
                    if alert.repair_attempts >= self.config["max_repair_attempts"]:
                        self._send_to_sandbox(alert)
            except Exception as e:
                logger.error(f"Error reparando alerta crítica: {e}")
                self._send_to_sandbox(alert)

    def _handle_medium(self, alert: Alert):
        """Manejar errores medios"""
        if self.config["auto_repair_enabled"] and self.repair_callback:
            try:
                alert.status = ErrorStatus.REPAIRING
                success = self.repair_callback(alert)

                if success:
                    alert.status = ErrorStatus.TEMPORARILY_FIXED
                    alert.fix_tag = self._generate_fix_tag(alert)
                    self._save_error_tags()

                    if not self.silent_mode:
                        logger.info(f"Alerta {alert.id} solucionada temporalmente")
                else:
                    alert.repair_attempts += 1
                    if alert.repair_attempts >= self.config["max_repair_attempts"]:
                        self._send_to_sandbox(alert)
            except Exception as e:
                logger.error(f"Error reparando alerta media: {e}")

    def _handle_low(self, alert: Alert):
        """Manejar errores bajos"""
        # Solo marcar como detected, reparación programada
        alert.status = ErrorStatus.DETECTED
        if not self.silent_mode:
            logger.info(f"Alerta {alert.id} (baja) detectada, reparación programada")

    def _send_to_sandbox(self, alert: Alert):
        """Enviar alerta al sandbox"""
        alert.status = ErrorStatus.SANDBOX

        if self.config["sandbox_enabled"] and self.sandbox_callback:
            try:
                self.sandbox_callback(alert)
                if not self.silent_mode:
                    logger.info(f"Alerta {alert.id} enviada al sandbox")
            except Exception as e:
                logger.error(f"Error enviando al sandbox: {e}")
                alert.status = ErrorStatus.FAILED
        else:
            alert.status = ErrorStatus.FAILED

    def _generate_fix_tag(self, alert: Alert) -> str:
        """Generar etiqueta de arreglo"""
        tag = f"{alert.source}_{alert.error_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Guardar en error_tags
        self.error_tags[tag] = {
            "alert_id": alert.id,
            "source": alert.source,
            "error_type": alert.error_type,
            "timestamp": datetime.now().isoformat(),
            "context": alert.context,
            "status": "temporarily_fixed",
        }

        return tag

    def create_alert(
        self,
        source: str,
        error_type: str,
        message: str,
        priority: ErrorPriority = ErrorPriority.MEDIUM,
        context: dict | None = None,
    ) -> str:
        """Crear nueva alerta"""
        alert_id = f"alert_{int(time.time() * 1000)}"

        alert = Alert(
            id=alert_id,
            source=source,
            error_type=error_type,
            message=message,
            priority=priority,
            status=ErrorStatus.DETECTED,
            timestamp=datetime.now().isoformat(),
            context=context or {},
        )

        self.alert_queue.put(alert)

        if not self.silent_mode:
            logger.info(f"Alerta creada: {alert_id} - {error_type}")

        return alert_id

    def get_active_alerts(self) -> list[Alert]:
        """Obtener alertas activas"""
        return list(self.active_alerts.values())

    def get_alert_by_id(self, alert_id: str) -> Alert | None:
        """Obtener alerta por ID"""
        return self.active_alerts.get(alert_id)

    def mark_resolved(self, alert_id: str):
        """Marcar alerta como resuelta"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = ErrorStatus.RESOLVED

            # Actualizar error_tags
            if alert.fix_tag and alert.fix_tag in self.error_tags:
                self.error_tags[alert.fix_tag]["status"] = "resolved"
                self._save_error_tags()

            if not self.silent_mode:
                logger.info(f"Alerta {alert_id} marcada como resuelta")

    def get_error_tags(self) -> dict:
        """Obtener todas las etiquetas de errores"""
        return self.error_tags


def main():
    """Punto de entrada CLI"""
    parser = argparse.ArgumentParser(description="URA - Gestor de Alertas")
    parser.add_argument("--start", action="store_true", help="Iniciar gestor")
    parser.add_argument("--silent", action="store_true", help="Modo silencioso")
    parser.add_argument("--verbose", action="store_true", help="Modo verboso")
    parser.add_argument("--list", action="store_true", help="Listar alertas activas")
    parser.add_argument("--tags", action="store_true", help="Listar etiquetas de errores")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    silent_mode = args.silent or (not args.verbose)

    if args.start:
        manager = AlertManager(silent_mode=silent_mode)
        manager.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            manager.stop()

    elif args.list:
        manager = AlertManager(silent_mode=True)
        alerts = manager.get_active_alerts()
        print(f"\n=== ALERTAS ACTIVAS ({len(alerts)}) ===")
        for alert in alerts:
            print(f"ID: {alert.id}")
            print(f"  Fuente: {alert.source}")
            print(f"  Tipo: {alert.error_type}")
            print(f"  Prioridad: {alert.priority.value}")
            print(f"  Estado: {alert.status.value}")
            print(f"  Mensaje: {alert.message}")
            print()

    elif args.tags:
        manager = AlertManager(silent_mode=True)
        tags = manager.get_error_tags()
        print(f"\n=== ETIQUETAS DE ERRORES ({len(tags)}) ===")
        for tag, data in tags.items():
            print(f"Tag: {tag}")
            print(f"  Estado: {data['status']}")
            print(f"  Timestamp: {data['timestamp']}")
            print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
