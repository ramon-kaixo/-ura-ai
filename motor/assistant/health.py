"""Health registry for the assistant module.

Separado de main.py para evitar circular imports (api ↔ main).
"""

from motor.observability.health import HealthRegistry

_registry = HealthRegistry()


def get_assistant_health() -> HealthRegistry:
    return _registry


def init_assistant_health() -> None:
    _registry.register_component("llm")
    _registry.register_component("memory")
    _registry.register_component("rag")
    _registry.register_component("conversation")
    _registry.set_healthy("llm", "initialized")
    _registry.set_healthy("memory", "initialized")
    _registry.set_healthy("rag", "initialized")
    _registry.set_healthy("conversation", "initialized")
