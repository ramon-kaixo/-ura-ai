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


def check_health_alert() -> list[str]:
    """Retorna alertas si health esta degradado o unhealthy."""
    import logging

    log = logging.getLogger("ura.health")
    registry = get_assistant_health()
    snapshot = registry.snapshot()
    alerts: list[str] = []
    for name, info in snapshot.get("components", {}).items():
        status = info.get("status", "")
        if status in ("degraded", "unhealthy"):
            msg = f"HEALTH ALERT: {name}={status}"
            log.warning(msg)
            alerts.append(msg)
    if not alerts:
        log.info("health: all %d components OK", len(snapshot.get("components", {})))
    return alerts
