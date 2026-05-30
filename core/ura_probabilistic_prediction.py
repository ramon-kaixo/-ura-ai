#!/usr/bin/env python3
"""
Predicción probabilística de URA - Nivel 16

Predicciones con probabilidades en lugar de binario:
- Evaluación de incertidumbre en decisiones
- Ajuste de confianza según datos disponibles
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROBABILISTIC_PREDICTION_PATH = Path.home() / ".ura" / "probabilistic_prediction.json"
PROBABILISTIC_PREDICTION_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Prediction:
    """Predicción probabilística."""

    event: str
    probability: float  # 0-1
    confidence: float  # 0-1
    evidence: list[str]
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Prediction":
        return cls(**data)


class URAProbabilisticPrediction:
    """Gestor de predicción probabilística de URA."""

    def __init__(self):
        self.predictions = self._load_predictions()

    def _load_predictions(self) -> list[Prediction]:
        """Cargar predicciones desde disco."""
        predictions = []
        if PROBABILISTIC_PREDICTION_PATH.exists():
            try:
                with open(PROBABILISTIC_PREDICTION_PATH) as f:
                    data = json.load(f)
                    predictions = [Prediction.from_dict(p) for p in data.get("predictions", [])]
            except Exception as e:
                logger.error(f"Error cargando predicciones: {e}")
        return predictions

    def _save_predictions(self):
        """Guardar predicciones a disco."""
        with open(PROBABILISTIC_PREDICTION_PATH, "w") as f:
            json.dump({"predictions": [p.to_dict() for p in self.predictions]}, f, indent=2)

    def predict(self, event: str, evidence: list[str]) -> dict:
        """Predice probabilidad de un evento basado en evidencia."""
        # Simplificado: probabilidad basada en cantidad de evidencia
        base_probability = 0.5
        evidence_boost = min(len(evidence) * 0.1, 0.4)
        probability = base_probability + evidence_boost

        # Confianza basada en calidad de evidencia
        confidence = min(len(evidence) * 0.15, 0.9)

        prediction = Prediction(
            event=event,
            probability=min(probability, 1.0),
            confidence=confidence,
            evidence=evidence,
            timestamp=datetime.now().isoformat(),
        )

        self.predictions.append(prediction)

        # Mantener solo últimas 100 predicciones
        if len(self.predictions) > 100:
            self.predictions = self.predictions[-100:]

        self._save_predictions()

        return {
            "event": event,
            "probability": probability,
            "confidence": confidence,
            "uncertainty": 1 - confidence,
        }

    def get_prediction_context(self) -> str:
        """Genera contexto de predicción para el system prompt."""
        recent_predictions = self.predictions[-3:] if self.predictions else []

        if not recent_predictions:
            return ""

        context_parts = ["PREDICCIÓN PROBABILÍSTICA:"]
        for pred in recent_predictions:
            context_parts.append(
                f"- {pred.event}: {pred.probability:.0%} probabilidad (confianza: {pred.confidence:.0%})"
            )

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_probabilistic_prediction: URAProbabilisticPrediction | None = None


def get_ura_probabilistic_prediction() -> URAProbabilisticPrediction:
    """Obtener el singleton de predicción probabilística de URA."""
    global _ura_probabilistic_prediction
    if _ura_probabilistic_prediction is None:
        _ura_probabilistic_prediction = URAProbabilisticPrediction()
    return _ura_probabilistic_prediction


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    prob = get_ura_probabilistic_prediction()

    # Prueba
    result = prob.predict(
        "Usuario pedirá ayuda con código",
        ["Usuario preguntó por código antes", "Hora habitual de trabajo"],
    )
    print("Predicción probabilística creada")
    print(result)
    print(prob.get_prediction_context())
