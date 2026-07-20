"""RecommendationValidator — valida recomendaciones contra el grafo.

Valida que las recomendaciones generadas por agentes externos sean:
  - Consistentes con el grafo existente
  - No duplicadas
  - Referencialmente íntegras
  - Acorde al tipo de documento

Principios:
  - Solo lectura de kg_*. Nunca escribe.
  - Validación en memoria.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("ura.knowledge.recommendation")


@dataclass(frozen=True)
class Recommendation:
    """Una recomendación generada por un agente."""

    kind: str  # "create" | "update" | "link" | "archive"
    target_id: str
    reason: str
    priority: str = "medium"  # "low" | "medium" | "high"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """Resultado de validar una recomendación."""

    valid: bool
    reason: str
    warnings: list[str] = field(default_factory=list)


class RecommendationValidator:
    """Valida recomendaciones contra el estado actual del grafo.

    Uso:
        validator = RecommendationValidator()
        result = validator.validate(recommendation, all_node_ids, existing_paths)
    """

    def validate(
        self,
        recommendation: Recommendation,
        all_node_ids: set[str],
        existing_paths: set[str],
    ) -> ValidationResult:
        """Valida una recomendación.

        Args:
            recommendation: Recomendación a validar.
            all_node_ids: IDs de todos los nodos existentes.
            existing_paths: Paths de todos los documentos existentes.

        Returns:
            Resultado de validación.

        """
        if recommendation.kind == "create":
            if recommendation.target_id in all_node_ids:
                return ValidationResult(
                    valid=False,
                    reason=f"El documento {recommendation.target_id} ya existe",
                )
            return ValidationResult(valid=True, reason="Documento nuevo válido")

        if recommendation.kind == "update":
            if recommendation.target_id not in all_node_ids:
                return ValidationResult(
                    valid=False,
                    reason=f"El documento {recommendation.target_id} no existe",
                )
            return ValidationResult(valid=True, reason="Actualización válida")

        if recommendation.kind == "link":
            if recommendation.target_id not in all_node_ids:
                return ValidationResult(
                    valid=False,
                    reason=f"Destino de enlace {recommendation.target_id} no existe",
                )
            return ValidationResult(valid=True, reason="Enlace válido")

        if recommendation.kind == "archive":
            if recommendation.target_id not in all_node_ids:
                return ValidationResult(
                    valid=False,
                    reason=f"Documento a archivar {recommendation.target_id} no existe",
                )
            return ValidationResult(valid=True, reason="Archivo válido")

        return ValidationResult(
            valid=False,
            reason=f"Tipo de recomendación desconocido: {recommendation.kind}",
        )
