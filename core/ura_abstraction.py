#!/usr/bin/env python3
"""
Capacidad de abstracción de URA - Nivel 13

URA crea conceptos abstractos y los conecta:
- Generaliza de casos específicos a principios
- Aplica principios abstractos a nuevas situaciones
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ABSTRACTION_PATH = Path.home() / ".ura" / "abstraction.json"
ABSTRACTION_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class AbstractConcept:
    """Concepto abstracto."""

    name: str
    description: str
    examples: list[str]  # Casos específicos que generaliza
    principles: list[str]  # Principios derivados
    confidence: float  # 0-1
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AbstractConcept":
        return cls(**data)


class URAAbstraction:
    """Gestor de capacidad de abstracción de URA."""

    def __init__(self):
        self.concepts = self._load_concepts()

    def _load_concepts(self) -> list[AbstractConcept]:
        """Cargar conceptos desde disco."""
        concepts = []
        if ABSTRACTION_PATH.exists():
            try:
                with open(ABSTRACTION_PATH) as f:
                    data = json.load(f)
                    concepts = [AbstractConcept.from_dict(c) for c in data.get("concepts", [])]
            except Exception as e:
                logger.error(f"Error cargando conceptos: {e}")

        # Si no hay conceptos, crear los por defecto
        if not concepts:
            concepts = self._create_default_concepts()

        return concepts

    def _create_default_concepts(self) -> list[AbstractConcept]:
        """Crear conceptos por defecto."""
        now = datetime.now().isoformat()
        return [
            AbstractConcept(
                name="seguridad",
                description="Proteger datos y privacidad",
                examples=["backup encriptado", "autenticación", "validación de inputs"],
                principles=[
                    "Siempre verificar antes de modificar datos críticos",
                    "Usar encriptación para información sensible",
                ],
                confidence=0.9,
                created_at=now,
            ),
            AbstractConcept(
                name="eficiencia",
                description="Optimizar tiempo y recursos",
                examples=["automatización de tareas", "caching", "batch processing"],
                principles=[
                    "Automatizar tareas repetitivas",
                    "Reutilizar recursos cuando sea posible",
                ],
                confidence=0.8,
                created_at=now,
            ),
        ]

    def _save_concepts(self):
        """Guardar conceptos a disco."""
        with open(ABSTRACTION_PATH, "w") as f:
            json.dump({"concepts": [c.to_dict() for c in self.concepts]}, f, indent=2)

    def extract_principle(self, specific_case: str) -> str | None:
        """Extraer principio de un caso específico."""
        # Simplificado: buscar palabras clave en el caso
        case_lower = specific_case.lower()

        if "seguro" in case_lower or "proteger" in case_lower:
            return "Verificar seguridad antes de proceder"
        elif "rápido" in case_lower or "eficiente" in case_lower:
            return "Optimizar para eficiencia"
        elif "automático" in case_lower:
            return "Automatizar cuando sea posible"

        return None

    def apply_principle(self, principle: str, situation: str) -> str:
        """Aplicar un principio abstracto a una situación."""
        # Simplificado: generar recomendación
        return f"Aplicando principio '{principle}' a: {situation}"

    def get_abstraction_context(self) -> str:
        """Genera contexto de abstracción para el system prompt."""
        context_parts = ["CAPACIDAD DE ABSTRACIÓN:"]

        for concept in self.concepts[:3]:
            context_parts.append(f"- {concept.name}: {concept.description}")
            if concept.principles:
                context_parts.append(f"  Principio: {concept.principles[0]}")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_abstraction: URAAbstraction | None = None


def get_ura_abstraction() -> URAAbstraction:
    """Obtener el singleton de capacidad de abstracción de URA."""
    global _ura_abstraction
    if _ura_abstraction is None:
        _ura_abstraction = URAAbstraction()
    return _ura_abstraction


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    abstraction = get_ura_abstraction()

    # Prueba
    principle = abstraction.extract_principle("Crear backup seguro de datos")
    print("Capacidad de abstracción creada")
    print(f"Principio extraído: {principle}")
    print(abstraction.get_abstraction_context())
