#!/usr/bin/env python3
"""
Módulo: core/ura_anticipation.py
Propósito: Sistema de anticipación: detecta patrones de uso diarios y horarios para generar predicciones.
Dependencias principales: datetime, json, pathlib, threading
Reglas especiales: Comparar patrones con formato HH:MM usando split. Validar antes de convertir a int.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from core.ura_monitoring import get_ura_monitoring

logger = logging.getLogger(__name__)
monitor = get_ura_monitoring()

ANTICIPATION_PATH = Path.home() / ".ura" / "anticipation.json"
ANTICIPATION_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Pattern:
    """Patrón detectado."""

    pattern_type: str  # daily, weekly, hourly
    pattern_value: str  # valor específico del patrón
    action: str  # acción que suele seguir
    frequency: int
    last_seen: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Pattern":
        return cls(**data)


@dataclass
class Anticipation:
    """Anticipación generada."""

    anticipated_need: str
    confidence: float  # 0-1
    based_on: str
    suggested_action: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Anticipation":
        return cls(**data)


class URAAnticipation:
    """Gestor de anticipación de URA."""

    def __init__(self):
        self.patterns = self._load_patterns()
        self.anticipations = []
        self.action_history = []

    def _load_patterns(self) -> list[Pattern]:
        """Cargar patrones desde disco."""
        patterns = []
        if ANTICIPATION_PATH.exists():
            try:
                with open(ANTICIPATION_PATH) as f:
                    data = json.load(f)
                    patterns = [Pattern.from_dict(p) for p in data.get("patterns", [])]
            except Exception as e:
                logger.error(f"Error cargando patrones: {e}")
        return patterns

    def _save_patterns(self):
        """Guardar patrones a disco."""
        with open(ANTICIPATION_PATH, "w") as f:
            json.dump({"patterns": [p.to_dict() for p in self.patterns]}, f, indent=2)

    def record_action(self, action: str, timestamp: str = None):
        """Registrar acción para detección de patrones."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        dt = datetime.fromisoformat(timestamp)

        self.action_history.append(
            {
                "timestamp": timestamp,
                "action": action,
                "day_of_week": dt.strftime("%A"),  # Monday, Tuesday, etc.
                "hour": dt.hour,
            }
        )

        # Mantener solo últimos 1000 acciones
        if len(self.action_history) > 1000:
            self.action_history = self.action_history[-1000:]

        # Actualizar patrones
        self._update_patterns()

    def _update_patterns(self):
        """Actualizar patrones basados en historial de acciones."""
        start = time.time()

        if len(self.action_history) < 10:
            return  # Necesitas al menos 10 acciones para detectar patrones

        # Detectar patrones de día de la semana
        day_actions = {}
        for entry in self.action_history:
            day = entry["day_of_week"]
            action = entry["action"]
            key = f"{day}:{action}"
            day_actions[key] = day_actions.get(key, 0) + 1

        # Detectar patrones de hora
        hour_actions = {}
        for entry in self.action_history:
            hour = entry["hour"]
            action = entry["action"]
            key = f"{hour}:{action}"
            hour_actions[key] = hour_actions.get(key, 0) + 1

        # Actualizar patrones (solo si frecuencia >= 3)
        self.patterns = []

        for key, count in day_actions.items():
            if count >= 3:
                day, action = key.split(":", 1)
                self.patterns.append(
                    Pattern(
                        pattern_type="daily",
                        pattern_value=day,
                        action=action,
                        frequency=count,
                        last_seen=datetime.now().isoformat(),
                    )
                )

        for key, count in hour_actions.items():
            if count >= 3:
                hour, action = key.split(":", 1)
                self.patterns.append(
                    Pattern(
                        pattern_type="hourly",
                        pattern_value=f"{hour}:00",
                        action=action,
                        frequency=count,
                        last_seen=datetime.now().isoformat(),
                    )
                )

        duration = time.time() - start
        monitor.log_performance("anticipation", "_update_patterns", duration)

        self._save_patterns()

    def generate_anticipations(self) -> list[Anticipation]:
        """Generar anticipaciones basadas en patrones y contexto actual."""
        self.anticipations = []
        now = datetime.now()
        current_day = now.strftime("%A")
        current_hour = now.hour

        # Anticipar basado en día de la semana
        for pattern in self.patterns:
            if pattern.pattern_type == "daily" and pattern.pattern_value == current_day:
                confidence = min(pattern.frequency / 10, 0.9)  # Max 0.9
                self.anticipations.append(
                    Anticipation(
                        anticipated_need=pattern.action,
                        confidence=confidence,
                        based_on=f"Patrón semanal: {pattern.pattern_value} ({pattern.frequency} veces)",
                        suggested_action=f"Preparar para: {pattern.action}",
                    )
                )

            # Anticipar basado en hora (±1 hora)
            if pattern.pattern_type == "hourly":
                try:
                    pattern_hour = int(pattern.pattern_value.split(":")[0])
                except (ValueError, IndexError):
                    pattern_hour = current_hour
                if abs(current_hour - pattern_hour) <= 1:
                    confidence = min(pattern.frequency / 10, 0.8)
                    self.anticipations.append(
                        Anticipation(
                            anticipated_need=pattern.action,
                            confidence=confidence,
                            based_on=f"Patrón horario: {pattern.pattern_value}:00 ({pattern.frequency} veces)",
                            suggested_action=f"Preparar para: {pattern.action}",
                        )
                    )

        return self.anticipations

    def get_context_for_prompt(self) -> str:
        """Generar contexto para el system prompt."""
        anticipations = self.generate_anticipations()

        if not anticipations:
            return ""

        context_parts = ["ANTICIPACIÓN (basada en patrones detectados):"]
        for ant in anticipations[:3]:  # Máximo 3 anticipaciones
            context_parts.append(f"- {ant.anticipated_need} ({ant.confidence:.0%} confianza)")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_anticipation: URAAnticipation | None = None


def get_ura_anticipation() -> URAAnticipation:
    """Obtener el singleton de anticipación de URA."""
    global _ura_anticipation
    if _ura_anticipation is None:
        _ura_anticipation = URAAnticipation()
    return _ura_anticipation


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    anticipation = get_ura_anticipation()

    # Prueba
    anticipation.record_action("consultar estado del sistema")
    anticipation.record_action("consultar estado del sistema")
    anticipation.record_action("consultar estado del sistema")

    print("Anticipación creada")
    print(anticipation.get_context_for_prompt())
