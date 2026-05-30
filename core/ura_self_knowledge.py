#!/usr/bin/env python3
"""
Auto-conocimiento de URA - Capa 2

URA sabe en cada momento:
- Qué módulos están funcionando y cuáles no
- Qué ha hecho en las últimas 24 horas
- Qué errores ha cometido y cómo los resolvió
- Cuánto ha mejorado con el tiempo
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

SELF_KNOWLEDGE_DIR = Path.home() / ".ura" / "self_knowledge"
SELF_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ModuleStatus:
    """Estado de un módulo."""

    name: str
    status: str  # running, stopped, error
    last_check: str
    uptime: str = "0s"
    errors: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ModuleStatus":
        return cls(**data)


@dataclass
class ActivityLog:
    """Registro de actividad de URA."""

    timestamp: str
    action: str
    result: str
    duration: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ActivityLog":
        return cls(**data)


@dataclass
class ErrorRecord:
    """Registro de error de URA."""

    timestamp: str
    error_type: str
    error_message: str
    resolution: str = ""
    resolved: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorRecord":
        return cls(**data)


@dataclass
class ImprovementMetric:
    """Métrica de mejora."""

    date: str
    metric_name: str
    value: float
    previous_value: float
    improvement: float  # positive = improvement

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ImprovementMetric":
        return cls(**data)


class URASelfKnowledge:
    """Auto-conocimiento de URA - Capa 2."""

    def __init__(self):
        self.modules_file = SELF_KNOWLEDGE_DIR / "modules.json"
        self.activity_file = SELF_KNOWLEDGE_DIR / "activity.jsonl"
        self.errors_file = SELF_KNOWLEDGE_DIR / "errors.jsonl"
        self.metrics_file = SELF_KNOWLEDGE_DIR / "metrics.jsonl"

        self.modules = self._load_modules()
        self.activity = self._load_activity()
        self.errors = self._load_errors()
        self.metrics = self._load_metrics()

    def _load_modules(self) -> list[ModuleStatus]:
        """Cargar estado de módulos."""
        modules = []
        if self.modules_file.exists():
            try:
                with open(self.modules_file) as f:
                    data = json.load(f)
                    modules = [ModuleStatus.from_dict(m) for m in data]
            except Exception as e:
                logger.error(f"Error cargando módulos: {e}")
        return modules

    def _load_activity(self) -> list[ActivityLog]:
        """Cargar actividad de las últimas 24h."""
        activity = []
        if self.activity_file.exists():
            try:
                cutoff = datetime.now() - timedelta(hours=24)
                with open(self.activity_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            log = ActivityLog.from_dict(data)
                            # Solo últimas 24h
                            if datetime.fromisoformat(log.timestamp) >= cutoff:
                                activity.append(log)
            except Exception as e:
                logger.error(f"Error cargando actividad: {e}")
        return activity

    def _load_errors(self) -> list[ErrorRecord]:
        """Cargar errores recientes."""
        errors = []
        if self.errors_file.exists():
            try:
                with open(self.errors_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            errors.append(ErrorRecord.from_dict(data))
            except Exception as e:
                logger.error(f"Error cargando errores: {e}")
        return errors

    def _load_metrics(self) -> list[ImprovementMetric]:
        """Cargar métricas de mejora."""
        metrics = []
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            metrics.append(ImprovementMetric.from_dict(data))
            except Exception as e:
                logger.error(f"Error cargando métricas: {e}")
        return metrics

    def update_module_status(self, module_name: str, status: str, errors: int = 0):
        """Actualizar estado de módulo."""
        now = datetime.now().isoformat()
        module = next((m for m in self.modules if m.name == module_name), None)
        if module:
            module.status = status
            module.last_check = now
            module.errors = errors
        else:
            self.modules.append(
                ModuleStatus(name=module_name, status=status, last_check=now, errors=errors)
            )
        self._save_modules()

    def log_activity(self, action: str, result: str, duration: str = ""):
        """Registrar actividad."""
        log = ActivityLog(
            timestamp=datetime.now().isoformat(), action=action, result=result, duration=duration
        )
        self.activity.append(log)
        with open(self.activity_file, "a") as f:
            f.write(json.dumps(log.to_dict()) + "\n")

    def log_error(self, error_type: str, error_message: str, resolution: str = ""):
        """Registrar error."""
        error = ErrorRecord(
            timestamp=datetime.now().isoformat(),
            error_type=error_type,
            error_message=error_message,
            resolution=resolution,
        )
        self.errors.append(error)
        with open(self.errors_file, "a") as f:
            f.write(json.dumps(error.to_dict()) + "\n")

    def resolve_error(self, error_type: str, resolution: str):
        """Marcar error como resuelto."""
        for error in self.errors:
            if error.error_type == error_type and not error.resolved:
                error.resolution = resolution
                error.resolved = True
                break
        self._save_errors()

    def record_metric(self, metric_name: str, value: float):
        """Registrar métrica de mejora."""
        # Obtener valor anterior
        previous_value = 0.0
        for metric in reversed(self.metrics):
            if metric.metric_name == metric_name:
                previous_value = metric.value
                break

        improvement = value - previous_value

        metric = ImprovementMetric(
            date=date.today().isoformat(),
            metric_name=metric_name,
            value=value,
            previous_value=previous_value,
            improvement=improvement,
        )
        self.metrics.append(metric)
        with open(self.metrics_file, "a") as f:
            f.write(json.dumps(metric.to_dict()) + "\n")

    def _save_modules(self):
        """Guardar estado de módulos."""
        with open(self.modules_file, "w") as f:
            json.dump([m.to_dict() for m in self.modules], f, indent=2)

    def _save_errors(self):
        """Guardar errores."""
        with open(self.errors_file, "w") as f:
            for error in self.errors:
                f.write(json.dumps(error.to_dict()) + "\n")

    def get_summary_for_prompt(self) -> str:
        """Obtener resumen para el system prompt."""
        summary_parts = []

        # Módulos funcionando
        running_modules = [m.name for m in self.modules if m.status == "running"]
        stopped_modules = [m.name for m in self.modules if m.status == "stopped"]
        error_modules = [m.name for m in self.modules if m.status == "error"]

        if running_modules:
            summary_parts.append(f"✅ Módulos activos: {', '.join(running_modules[:3])}")
        if stopped_modules:
            summary_parts.append(f"⏸️ Módulos parados: {', '.join(stopped_modules[:2])}")
        if error_modules:
            summary_parts.append(f"❌ Módulos con error: {', '.join(error_modules[:2])}")

        # Actividad 24h
        recent_activity = len(self.activity)
        if recent_activity > 0:
            summary_parts.append(f"📊 Actividad 24h: {recent_activity} acciones")

        # Errores recientes
        recent_errors = [e for e in self.errors if not e.resolved]
        if recent_errors:
            summary_parts.append(f"⚠️ Errores pendientes: {len(recent_errors)}")

        # Mejoras recientes
        recent_metrics = [m for m in self.metrics if m.date == date.today().isoformat()]
        if recent_metrics:
            improvements = [f"{m.metric_name}: {m.improvement:+.1f}" for m in recent_metrics[:2]]
            summary_parts.append(f"📈 Mejoras: {', '.join(improvements)}")

        return " | ".join(summary_parts) if summary_parts else "Sin datos de auto-conocimiento."


# Singleton
_ura_self_knowledge: URASelfKnowledge | None = None


def get_ura_self_knowledge() -> URASelfKnowledge:
    """Obtener el singleton de auto-conocimiento de URA."""
    global _ura_self_knowledge
    if _ura_self_knowledge is None:
        _ura_self_knowledge = URASelfKnowledge()
    return _ura_self_knowledge


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    self_knowledge = get_ura_self_knowledge()

    # Prueba
    self_knowledge.update_module_status("vision", "running")
    self_knowledge.update_module_status("web_search", "running")
    self_knowledge.update_module_status("email_search", "stopped")
    self_knowledge.log_activity("Consultar disco", "OK", "0.5s")
    self_knowledge.record_metric("response_time", 2.3)

    print("Auto-conocimiento de URA creado")
    print(self_knowledge.get_summary_for_prompt())
