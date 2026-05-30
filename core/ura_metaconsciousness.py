#!/usr/bin/env python3
"""
Meta-conciencia de URA - Nivel 5

URA sabe qué sabe y qué no sabe:
- Reconoce límites de conocimiento
- Auto-evalúa sus propias respuestas
- Solicita más información cuando es necesario
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeBoundary:
    """Límite de conocimiento."""

    domain: str  # dominio de conocimiento
    confidence: float  # 0-1
    last_updated: str
    examples_known: list[str] = field(default_factory=list)
    examples_unknown: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeBoundary":
        return cls(**data)


class URAMetaconsciousness:
    """Gestor de meta-conciencia de URA."""

    def __init__(self, config_path: str | Path = None):
        """Inicializar meta-conciencia.

        Args:
            config_path: Ruta al archivo de configuración JSON
        """
        if config_path is None:
            config_path = Path.home() / ".ura" / "metaconsciousness.json"
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.knowledge_boundaries = self._load_boundaries()
        self.self_evaluations = []

    def _load_boundaries(self) -> dict[str, KnowledgeBoundary]:
        """Cargar límites de conocimiento desde disco."""
        boundaries = {}
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    for domain, boundary_data in data.get("boundaries", {}).items():
                        boundaries[domain] = KnowledgeBoundary.from_dict(boundary_data)
            except Exception as e:
                logger.error(f"Error cargando límites de conocimiento: {e}")
        return boundaries

    def _save_boundaries(self):
        """Guardar límites de conocimiento a disco."""
        with open(self.config_path, "w") as f:
            json.dump(
                {"boundaries": {k: v.to_dict() for k, v in self.knowledge_boundaries.items()}},
                f,
                indent=2,
            )

    def record_knowledge(self, domain: str, known: bool, example: str = ""):
        """Registrar conocimiento o desconocimiento en un dominio."""
        if domain not in self.knowledge_boundaries:
            self.knowledge_boundaries[domain] = KnowledgeBoundary(
                domain=domain, confidence=0.5, last_updated=datetime.now().isoformat()
            )

        boundary = self.knowledge_boundaries[domain]
        if known:
            boundary.examples_known.append(example)
            boundary.confidence = min(boundary.confidence + 0.1, 1.0)
        else:
            boundary.examples_unknown.append(example)
            boundary.confidence = max(boundary.confidence - 0.1, 0.0)

        boundary.last_updated = datetime.now().isoformat()
        self._save_boundaries()

    def evaluate_confidence(self, domain: str) -> float:
        """Evaluar nivel de confianza en un dominio."""
        if domain not in self.knowledge_boundaries:
            return 0.5  # Neutral si no tiene información
        return self.knowledge_boundaries[domain].confidence

    def should_request_info(self, domain: str, threshold: float = 0.3) -> bool:
        """Determinar si debe solicitar más información."""
        confidence = self.evaluate_confidence(domain)
        return confidence < threshold

    def self_evaluate(self, response: str, confidence: float, reasoning: str = ""):
        """Auto-evaluar una respuesta."""
        self.self_evaluations.append(
            {
                "timestamp": datetime.now().isoformat(),
                "response": response[:100],  # Primeros 100 caracteres
                "confidence": confidence,
                "reasoning": reasoning,
            }
        )

        # Mantener solo últimas 100 evaluaciones
        if len(self.self_evaluations) > 100:
            self.self_evaluations = self.self_evaluations[-100:]

    def get_uncertainty_context(self) -> str:
        """Genera contexto de incertidumbre para el system prompt."""
        uncertain_domains = [
            domain
            for domain, boundary in self.knowledge_boundaries.items()
            if boundary.confidence < 0.4
        ]

        if not uncertain_domains:
            return ""

        return f"""
META-CONCIENCIA (límites de conocimiento):
- Dominios con baja confianza: {", ".join(uncertain_domains[:3])}
- Si preguntas sobre estos temas, solicitaré más información antes de responder.
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    metaconsciousness = URAMetaconsciousness()

    # Prueba
    metaconsciousness.record_knowledge("sistema", True, "estado del disco")
    metaconsciousness.record_knowledge("finanzas", False, "estado del banco")
    metaconsciousness.self_evaluate("El disco tiene 33GB libres", 0.8, "Datos recientes")

    print("Meta-conciencia creada")
    print(metaconsciousness.get_uncertainty_context())
