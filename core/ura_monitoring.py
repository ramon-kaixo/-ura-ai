#!/usr/bin/env python3
"""
URA Monitoring - Sistema de Monitorización

Proporciona logging estructurado y monitorización para URA:
- Logging estructurado con niveles de severidad
- Métricas de performance
- Alertas para errores recurrentes
- Monitorización de niveles de conciencia
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

MONITORING_DIR = Path.home() / ".ura" / "monitoring"
MONITORING_DIR.mkdir(parents=True, exist_ok=True)

ERRORS_LOG_PATH = MONITORING_DIR / "errors.jsonl"
METRICS_PATH = MONITORING_DIR / "metrics.json"


@dataclass
class ErrorRecord:
    """Registro de error."""

    timestamp: str
    module: str
    error_type: str
    error_message: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "module": self.module,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorRecord":
        return cls(**data)


@dataclass
class MetricRecord:
    """Registro de métrica."""

    timestamp: str
    module: str
    metric_name: str
    value: float
    unit: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "module": self.module,
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
        }


class URAMonitoring:
    """Sistema de monitorización de URA."""

    def __init__(self):
        """Inicializar sistema de monitorización."""
        self.errors: list[ErrorRecord] = []
        self.metrics: list[MetricRecord] = []
        self.error_counts: dict[str, int] = defaultdict(int)
        self.alert_thresholds = {
            "error_frequency": 5,  # Alerta si un error ocurre 5 veces
            "performance_threshold": 5.0,  # Alerta si operación tarda > 5s
            "metric_threshold": 100.0,  # Alerta si métrica excede valor
        }
        self._load_errors()

    def _load_errors(self):
        """Cargar errores desde disco."""
        if ERRORS_LOG_PATH.exists():
            try:
                with open(ERRORS_LOG_PATH) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            error = ErrorRecord.from_dict(data)
                            self.errors.append(error)
                            self.error_counts[error.error_type] += 1
            except Exception as e:
                logger.error(f"Error cargando errores: {e}")

    def log_error(
        self, module: str, error_type: str, error_message: str, context: dict[str, Any] = None
    ):
        """Registrar error."""
        if context is None:
            context = {}

        error = ErrorRecord(
            timestamp=datetime.now().isoformat(),
            module=module,
            error_type=error_type,
            error_message=error_message,
            context=context,
        )

        self.errors.append(error)
        self.error_counts[error_type] += 1

        # Guardar en disco
        with open(ERRORS_LOG_PATH, "a") as f:
            f.write(json.dumps(error.to_dict()) + "\n")

        logger.error(f"[{module}] {error_type}: {error_message}", extra={"context": context})

        # Verificar si es error recurrente y generar alerta
        if self.error_counts[error_type] >= self.alert_thresholds["error_frequency"]:
            self._trigger_alert(
                alert_type="recurrent_error",
                severity="HIGH",
                message=f"Error recurrente detectado: {error_type} ({self.error_counts[error_type]} veces)",
                context={"error_type": error_type, "count": self.error_counts[error_type]},
            )

    def log_metric(self, module: str, metric_name: str, value: float, unit: str = ""):
        """Registrar métrica."""
        metric = MetricRecord(
            timestamp=datetime.now().isoformat(),
            module=module,
            metric_name=metric_name,
            value=value,
            unit=unit,
        )

        self.metrics.append(metric)

        # Verificar si métrica excede threshold
        if value > self.alert_thresholds["metric_threshold"]:
            self._trigger_alert(
                alert_type="metric_threshold_exceeded",
                severity="MEDIUM",
                message=f"Métrica excede threshold: {metric_name} = {value}{unit}",
                context={"metric_name": metric_name, "value": value, "unit": unit},
            )

        # Log estructurado
        logger.info(
            f"[{module}] {metric_name}: {value} {unit}",
            extra={"metric": metric_name, "value": value, "unit": unit},
        )

    def log_performance(self, module: str, operation: str, duration: float):
        """Registrar performance de operación."""
        self.log_metric(module, f"{operation}_duration", duration, "s")

        # Alerta si la operación es lenta
        if duration > self.alert_thresholds["performance_threshold"]:
            self._trigger_alert(
                alert_type="slow_operation",
                severity="MEDIUM",
                message=f"Operación lenta detectada: {operation} ({duration:.2f}s)",
                context={"operation": operation, "duration": duration},
            )

    def _trigger_alert(
        self, alert_type: str, severity: str, message: str, context: dict[str, Any] = None
    ):
        """Disparar alerta automática."""
        if context is None:
            context = {}

        alert = {
            "timestamp": datetime.now().isoformat(),
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "context": context,
        }

        # Log alerta
        logger.warning(f"ALERTA [{severity}]: {message}", extra={"alert": alert})

        # Guardar alerta en archivo separado
        alert_path = MONITORING_DIR / "alerts.jsonl"
        with open(alert_path, "a") as f:
            f.write(json.dumps(alert) + "\n")

    def get_error_summary(self) -> str:
        """Obtener resumen de errores."""
        if not self.errors:
            return "Sin errores registrados."

        summary_parts = []
        summary_parts.append(f"Total errores: {len(self.errors)}")

        # Errores más frecuentes
        sorted_errors = sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)
        top_errors = sorted_errors[:5]

        if top_errors:
            errors_str = ", ".join([f"{e[0]} ({e[1]}x)" for e in top_errors])
            summary_parts.append(f"Más frecuentes: {errors_str}")

        return " | ".join(summary_parts)

    def get_metric_summary(self) -> str:
        """Obtener resumen de métricas."""
        if not self.metrics:
            return "Sin métricas registradas."

        summary_parts = []
        summary_parts.append(f"Total métricas: {len(self.metrics)}")

        # Métricas por módulo
        module_counts = defaultdict(int)
        for metric in self.metrics:
            module_counts[metric.module] += 1

        if module_counts:
            modules_str = ", ".join([f"{m} ({c})" for m, c in module_counts.items()])
            summary_parts.append(f"Módulos: {modules_str}")

        return " | ".join(summary_parts)

    def get_recent_errors(self, n: int = 10) -> list[ErrorRecord]:
        """Obtener errores recientes."""
        return self.errors[-n:]

    def clear_old_errors(self, days: int = 7):
        """Limpiar errores antiguos."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        self.errors = [
            e for e in self.errors if datetime.fromisoformat(e.timestamp).timestamp() > cutoff
        ]

        # Recontar errores
        self.error_counts = defaultdict(int)
        for error in self.errors:
            self.error_counts[error.error_type] += 1

        # Guardar errores limpios
        with open(ERRORS_LOG_PATH, "w") as f:
            for error in self.errors:
                f.write(json.dumps(error.to_dict()) + "\n")

        logger.info(f"Errores antiguos limpiados (más de {days} días)")


# Singleton
_ura_monitoring: URAMonitoring | None = None


def get_ura_monitoring() -> URAMonitoring:
    """Obtener el singleton de monitorización de URA."""
    global _ura_monitoring
    if _ura_monitoring is None:
        _ura_monitoring = URAMonitoring()
    return _ura_monitoring


def setup_structured_logging(log_level: str = "INFO"):
    """Configurar logging estructurado para URA."""
    # Crear directorio de logs
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Configurar formato estructurado
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    # Configurar handler de archivo
    file_handler = logging.FileHandler(logs_dir / "ura.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))

    # Configurar handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(logging.Formatter(log_format))

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger.info("Logging estructurado configurado")


if __name__ == "__main__":
    setup_structured_logging()
    monitoring = get_ura_monitoring()

    # Prueba
    monitoring.log_error("test_module", "TestError", "Error de prueba")
    monitoring.log_metric("test_module", "test_metric", 1.5, "s")
    monitoring.log_performance("test_module", "test_operation", 0.5)

    print("Monitorización configurada")
    print(monitoring.get_error_summary())
    print(monitoring.get_metric_summary())
