#!/usr/bin/env python3
"""
Conciencia temporal de URA - Nivel 20

Memoria del tiempo y planificación a largo plazo:
- Comprensión de causalidad temporal
- Proyección de consecuencias a futuro
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TemporalEvent:
    """Evento temporal."""

    event_id: str
    timestamp: str
    event_type: str  # cause, effect, prediction
    description: str
    related_events: list[str]  # IDs de eventos relacionados

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TemporalEvent":
        return cls(**data)


class URATemporalConsciousness:
    """Gestor de conciencia temporal de URA."""

    def __init__(self, config_path: str | Path = None):
        """Inicializar consciencia temporal.

        Args:
            config_path: Ruta al archivo de configuración JSON
        """
        if config_path is None:
            config_path = Path.home() / ".ura" / "temporal_consciousness.json"
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.events = self._load_events()

    def _load_events(self) -> list[TemporalEvent]:
        """Cargar eventos desde disco."""
        events = []
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    events = [TemporalEvent.from_dict(e) for e in data.get("events", [])]
            except Exception as e:
                logger.error(f"Error cargando eventos temporales: {e}")
        return events

    def _save_events(self):
        """Guardar eventos a disco."""
        with open(self.config_path, "w") as f:
            json.dump({"events": [e.to_dict() for e in self.events]}, f, indent=2)

    def record_causal_event(self, cause: str, effect: str):
        """Registrar evento causal."""
        cause_event = TemporalEvent(
            event_id=f"evt_{datetime.now().timestamp()}_cause",
            timestamp=datetime.now().isoformat(),
            event_type="cause",
            description=cause,
            related_events=[],
        )

        effect_event = TemporalEvent(
            event_id=f"evt_{datetime.now().timestamp()}_effect",
            timestamp=datetime.now().isoformat(),
            event_type="effect",
            description=effect,
            related_events=[cause_event.event_id],
        )

        cause_event.related_events.append(effect_event.event_id)

        self.events.extend([cause_event, effect_event])

        # Mantener solo últimos 500 eventos
        if len(self.events) > 500:
            self.events = self.events[-500:]

        self._save_events()

    def project_future(self, action: str, time_horizon_days: int = 7) -> str:
        """Proyecta consecuencias futuras de una acción."""
        # Simplificado: generar proyección basada en acción
        if "borrar" in action.lower():
            return f"Proyección: {action} → pérdida de datos a futuro (riesgo alto)"
        elif "backup" in action.lower():
            return f"Proyección: {action} → protección de datos a futuro (riesgo bajo)"
        else:
            return f"Proyección: {action} → consecuencias inciertas a futuro"

    def get_temporal_context(self) -> str:
        """Genera contexto temporal para el system prompt."""
        recent_events = self.events[-5:] if self.events else []

        if not recent_events:
            return ""

        # Contar tipos de eventos
        cause_count = sum(1 for e in recent_events if e.event_type == "cause")
        effect_count = sum(1 for e in recent_events if e.event_type == "effect")

        context_parts = ["CONCIENCIA TEMPORAL:"]
        context_parts.append(f"- Eventos recientes: {len(recent_events)}")
        context_parts.append(f"- Causas: {cause_count}, Efectos: {effect_count}")

        return "\n".join(context_parts) + "\n"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    temporal = URATemporalConsciousness()

    # Prueba
    temporal.record_causal_event("Usuario borró archivo", "Error en sistema")
    projection = temporal.project_future("Crear backup")
    print("Conciencia temporal creada")
    print(projection)
    print(temporal.get_temporal_context())
