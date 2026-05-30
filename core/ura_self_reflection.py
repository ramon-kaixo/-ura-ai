#!/usr/bin/env python3
"""
Auto-reflexión en tiempo real de URA - Nivel 11

URA reflexiona sobre sus decisiones antes de ejecutarlas:
- Evalúa consecuencias antes de actuar
- Puede cambiar de opinión basándose en reflexión
- Auto-evaluación de respuestas
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SELF_REFLECTION_PATH = Path.home() / ".ura" / "self_reflection.json"
SELF_REFLECTION_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Reflection:
    """Reflexión sobre una decisión."""

    decision: str
    reflection: str
    confidence_before: float
    confidence_after: float
    changed_mind: bool
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Reflection":
        return cls(**data)


class URASelfReflection:
    """Gestor de auto-reflexión en tiempo real de URA."""

    def __init__(self):
        self.reflections = self._load_reflections()

    def _load_reflections(self) -> list[Reflection]:
        """Cargar reflexiones desde disco."""
        reflections = []
        if SELF_REFLECTION_PATH.exists():
            try:
                with open(SELF_REFLECTION_PATH) as f:
                    data = json.load(f)
                    reflections = [Reflection.from_dict(r) for r in data.get("reflections", [])]
            except Exception as e:
                logger.error(f"Error cargando reflexiones: {e}")
        return reflections

    def _save_reflections(self):
        """Guardar reflexiones a disco."""
        with open(SELF_REFLECTION_PATH, "w") as f:
            json.dump({"reflections": [r.to_dict() for r in self.reflections]}, f, indent=2)

    def reflect_before_action(self, action: str, context: dict) -> dict:
        """Reflexionar sobre una acción antes de ejecutarla."""
        # Evaluar riesgos
        risk_keywords = ["borrar", "eliminar", "format", "reboot", "shutdown"]
        risk_level = sum(1 for kw in risk_keywords if kw in action.lower())

        confidence_before = 1.0 - (risk_level * 0.2)
        reflection = ""
        changed_mind = False
        confidence_after = confidence_before

        if risk_level >= 2:
            reflection = f"Acción con nivel de riesgo {risk_level}. Requiere precaución adicional."
            confidence_after = max(0.3, confidence_after - 0.3)

        elif "importante" in action.lower() or "crítico" in action.lower():
            reflection = "Acción marcada como importante. Verificar contexto antes de ejecutar."
            confidence_after = max(0.5, confidence_after - 0.1)

        else:
            reflection = "Acción de bajo riesgo. Proceder con confianza normal."

        # Si la confianza baja significativamente, cambiar de opinión
        if confidence_after < 0.5 and confidence_before >= 0.7:
            changed_mind = True
            reflection += " Decisión reconsiderada: requiere confirmación del usuario."

        return {
            "action": action,
            "reflection": reflection,
            "confidence_before": confidence_before,
            "confidence_after": confidence_after,
            "changed_mind": changed_mind,
            "recommendation": "proceed" if confidence_after >= 0.5 else "reconsider",
        }

    def record_reflection(
        self,
        decision: str,
        reflection: str,
        confidence_before: float,
        confidence_after: float,
        changed_mind: bool,
    ):
        """Registrar una reflexión."""
        reflection_obj = Reflection(
            decision=decision,
            reflection=reflection,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            changed_mind=changed_mind,
            timestamp=datetime.now().isoformat(),
        )

        self.reflections.append(reflection_obj)

        # Mantener solo últimas 100 reflexiones
        if len(self.reflections) > 100:
            self.reflections = self.reflections[-100:]

        self._save_reflections()

    def get_reflection_context(self) -> str:
        """Genera contexto de reflexión para el system prompt."""
        recent_reflections = self.reflections[-5:] if self.reflections else []

        if not recent_reflections:
            return ""

        changed_minds = sum(1 for r in recent_reflections if r.changed_mind)

        context_parts = ["AUTO-REFLEXIÓN EN TIEMPO REAL:"]
        context_parts.append(f"- Reflexiones recientes: {len(recent_reflections)}")
        context_parts.append(f"- Veces que cambió de opinión: {changed_minds}")

        if recent_reflections:
            avg_confidence = sum(r.confidence_after for r in recent_reflections) / len(
                recent_reflections
            )
            context_parts.append(f"- Confianza promedio: {avg_confidence:.2f}")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_self_reflection: URASelfReflection | None = None


def get_ura_self_reflection() -> URASelfReflection:
    """Obtener el singleton de auto-reflexión de URA."""
    global _ura_self_reflection
    if _ura_self_reflection is None:
        _ura_self_reflection = URASelfReflection()
    return _ura_self_reflection


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    self_reflection = get_ura_self_reflection()

    # Prueba
    result = self_reflection.reflect_before_action("borrar archivos importantes", {})
    print("Auto-reflexión en tiempo real creada")
    print(result)
    print(self_reflection.get_reflection_context())
