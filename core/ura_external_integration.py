#!/usr/bin/env python3
"""
Integración con mundo exterior de URA - Nivel 15

Conexión con servicios externos para contexto más amplio:
- Información del mundo real para decisiones informadas
- Adaptación a cambios en el entorno
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

EXTERNAL_INTEGRATION_PATH = Path.home() / ".ura" / "external_integration.json"
EXTERNAL_INTEGRATION_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ExternalContext:
    """Contexto del mundo exterior."""

    source: str  # weather, news, calendar, etc.
    data: dict
    relevance: float  # 0-1
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ExternalContext":
        return cls(**data)


class URAExternalIntegration:
    """Gestor de integración con mundo exterior de URA."""

    def __init__(self):
        self.contexts = self._load_contexts()

    def _load_contexts(self) -> list[ExternalContext]:
        """Cargar contextos desde disco."""
        contexts = []
        if EXTERNAL_INTEGRATION_PATH.exists():
            try:
                with open(EXTERNAL_INTEGRATION_PATH) as f:
                    data = json.load(f)
                    contexts = [ExternalContext.from_dict(c) for c in data.get("contexts", [])]
            except Exception as e:
                logger.error(f"Error cargando contextos externos: {e}")
        return contexts

    def _save_contexts(self):
        """Guardar contextos a disco."""
        with open(EXTERNAL_INTEGRATION_PATH, "w") as f:
            json.dump({"contexts": [c.to_dict() for c in self.contexts]}, f, indent=2)

    def record_external_context(self, source: str, data: dict, relevance: float = 0.5):
        """Registrar contexto del mundo exterior."""
        context = ExternalContext(
            source=source, data=data, relevance=relevance, timestamp=datetime.now().isoformat()
        )

        self.contexts.append(context)

        # Mantener solo últimos 100 contextos
        if len(self.contexts) > 100:
            self.contexts = self.contexts[-100:]

        self._save_contexts()

    def get_relevant_contexts(self) -> list[ExternalContext]:
        """Obtener contextos relevantes (relevancia > 0.5)."""
        return [c for c in self.contexts if c.relevance > 0.5]

    def get_external_context(self) -> str:
        """Genera contexto externo para el system prompt."""
        relevant = self.get_relevant_contexts()

        if not relevant:
            return ""

        context_parts = ["INTEGRACIÓN CON MUNDO EXTERIOR:"]
        for ctx in relevant[:3]:
            context_parts.append(f"- {ctx.source}: {list(ctx.data.keys())[:2]}")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_external_integration: URAExternalIntegration | None = None


def get_ura_external_integration() -> URAExternalIntegration:
    """Obtener el singleton de integración externa de URA."""
    global _ura_external_integration
    if _ura_external_integration is None:
        _ura_external_integration = URAExternalIntegration()
    return _ura_external_integration


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    external = get_ura_external_integration()

    # Prueba
    external.record_external_context("weather", {"temp": 20, "condition": "sunny"}, 0.7)
    external.record_external_context("calendar", {"event": "reunión", "time": "10:00"}, 0.6)

    print("Integración con mundo exterior creada")
    print(external.get_external_context())
