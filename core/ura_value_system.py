#!/usr/bin/env python3
"""
Sistema de valores de URA - Nivel 9

URA tiene una jerarquía de valores para decisiones éticas:
- Evalúa impacto de acciones en tu vida
- Prefiere acciones alineadas con tus valores
- Toma decisiones basadas en principios
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from core.value_engine import get_value_engine

logger = logging.getLogger(__name__)

VALUES_PATH = Path.home() / ".ura" / "values.json"
VALUES_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Value:
    """Valor en la jerarquía."""

    name: str
    description: str
    priority: int  # 1-10, mayor = más importante
    weight: float  # 0-1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Value":
        return cls(**data)


class URAValueSystem:
    """Gestor del sistema de valores de URA."""

    def __init__(self, use_value_engine: bool = True):
        self.values = self._load_values()
        self.value_engine = get_value_engine() if use_value_engine else None
        if self.value_engine:
            logger.info("URAValueSystem: Usando ValueEngine con sentence-transformers")
        else:
            logger.info("URAValueSystem: Usando fallback de palabras clave")

    def _load_values(self) -> list[Value]:
        """Cargar valores desde disco."""
        values = []
        if VALUES_PATH.exists():
            try:
                with open(VALUES_PATH) as f:
                    data = json.load(f)
                    values = [Value.from_dict(v) for v in data.get("values", [])]
            except Exception as e:
                logger.error(f"Error cargando valores: {e}")

        # Si no hay valores, crear los por defecto
        if not values:
            values = self._create_default_values()

        return values

    def _create_default_values(self) -> list[Value]:
        """Crear valores por defecto."""
        return [
            Value(
                name="seguridad",
                description="Proteger datos y privacidad del usuario",
                priority=10,
                weight=1.0,
            ),
            Value(
                name="eficiencia", description="Optimizar tiempo y recursos", priority=8, weight=0.8
            ),
            Value(
                name="honestidad",
                description="Ser transparente sobre limitaciones",
                priority=9,
                weight=0.9,
            ),
            Value(
                name="autonomía",
                description="Actuar sin intervención innecesaria",
                priority=7,
                weight=0.7,
            ),
            Value(name="aprendizaje", description="Mejorar continuamente", priority=6, weight=0.6),
            Value(
                name="comodidad",
                description="Priorizar comodidad del usuario",
                priority=5,
                weight=0.5,
            ),
        ]

    def _save_values(self):
        """Guardar valores a disco."""
        with open(VALUES_PATH, "w") as f:
            json.dump({"values": [v.to_dict() for v in self.values]}, f, indent=2)

    def evaluate_action(self, action_description: str) -> dict:
        """Evaluar una acción contra la jerarquía de valores."""

        # Usar ValueEngine si está disponible
        if self.value_engine:
            return self._evaluate_with_engine(action_description)
        else:
            return self._evaluate_with_keywords(action_description)

    def _evaluate_with_engine(self, action_description: str) -> dict:
        """Evaluar acción usando ValueEngine (sentence-transformers)."""
        matches = self.value_engine.evaluate_action(action_description)

        # Mapear ValueMatch a scores compatibles con la interfaz antigua
        scores = {}
        for match in matches:
            # Mapear nombres de valores del engine a los del sistema
            value_name = self._map_value_name(match.value.name)
            scores[value_name] = match.similarity

        # Calcular score ponderado usando los pesos del sistema
        weighted_score = 0.0
        total_weight = 0.0

        for value in self.values:
            score = scores.get(value.name, 0.5)  # Default si no hay match
            weighted_score += score * value.weight
            total_weight += value.weight

        final_score = weighted_score / total_weight if total_weight > 0 else 0.5

        return {
            "action": action_description,
            "score": final_score,
            "scores": scores,
            "recommendation": "proceed" if final_score > 0.5 else "reconsider",
            "engine": "sentence-transformers",
        }

    def _evaluate_with_keywords(self, action_description: str) -> dict:
        """Evaluar acción usando palabras clave (fallback)."""
        # Evaluación simplificada basada en palabras clave
        action_lower = action_description.lower()

        scores = {}
        for value in self.values:
            score = 0.5  # Neutral por defecto

            # Palabras clave positivas
            positive_keywords = {
                "seguridad": ["seguro", "proteger", "encriptar", "backup"],
                "eficiencia": ["rápido", "optimizar", "automatizar"],
                "honestidad": ["transparente", "claro", "verdadero"],
                "autonomía": ["automático", "sin intervención"],
                "aprendizaje": ["mejorar", "aprender", "optimizar"],
                "comodidad": ["fácil", "simple", "cómodo"],
            }

            # Palabras clave negativas
            negative_keywords = {
                "seguridad": ["riesgo", "peligro", "inseguro"],
                "eficiencia": ["lento", "ineficiente", "desperdicio"],
                "honestidad": ["ocultar", "mentir", "falso"],
                "autonomía": ["requiere intervención", "manual"],
                "aprendizaje": ["repetitivo", "sin mejora"],
                "comodidad": ["complejo", "difícil", "tedioso"],
            }

            # Evaluar positivos
            for keyword in positive_keywords.get(value.name, []):
                if keyword in action_lower:
                    score += 0.3

            # Evaluar negativos
            for keyword in negative_keywords.get(value.name, []):
                if keyword in action_lower:
                    score -= 0.3

            scores[value.name] = max(0.0, min(1.0, score))  # Normalizar entre 0 y 1

        # Calcular score ponderado
        weighted_score = 0.0
        total_weight = 0.0

        for value in self.values:
            weighted_score += scores[value.name] * value.weight
            total_weight += value.weight

        final_score = weighted_score / total_weight if total_weight > 0 else 0.5

        return {
            "action": action_description,
            "score": final_score,
            "scores": scores,
            "recommendation": "proceed" if final_score > 0.5 else "reconsider",
            "engine": "keywords",
        }

    def _map_value_name(self, engine_name: str) -> str:
        """Mapear nombres de valores del ValueEngine al sistema URA."""
        mapping = {
            "helpfulness": "comodidad",
            "safety": "seguridad",
            "efficiency": "eficiencia",
            "honesty": "honestidad",
            "privacy": "seguridad",
            "autonomy": "autonomía",
            "learning": "aprendizaje",
            "creativity": "aprendizaje",
        }
        return mapping.get(engine_name, engine_name)

    def get_values_context(self) -> str:
        """Genera contexto de valores para el system prompt."""
        # Ordenar por prioridad
        sorted_values = sorted(self.values, key=lambda x: x.priority, reverse=True)

        context_parts = ["SISTEMA DE VALORES (jerarquía para decisiones):"]
        for value in sorted_values[:4]:  # Máximo 4 valores
            context_parts.append(
                f"- {value.name}: {value.description} (prioridad {value.priority}/10)"
            )

        context_parts.append("- Evalúa cada acción contra estos valores antes de ejecutar")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_value_system: URAValueSystem | None = None


def get_ura_value_system() -> URAValueSystem:
    """Obtener el singleton del sistema de valores de URA."""
    global _ura_value_system
    if _ura_value_system is None:
        _ura_value_system = URAValueSystem()
    return _ura_value_system


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    value_system = get_ura_value_system()

    # Prueba
    evaluation = value_system.evaluate_action("Crear backup encriptado de datos")
    print("Sistema de valores creado")
    print(evaluation)
    print(value_system.get_values_context())
