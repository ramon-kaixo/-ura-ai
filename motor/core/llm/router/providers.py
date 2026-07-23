"""Provider resolution for LLM router."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.llm.registry import ProviderRegistry

log = __import__("logging").getLogger(__name__)

DEFAULT_ROUTES: dict[str, str] = {
    "generate": "ollama",
    "embed": "ollama",
    "health": "ollama",
}


def resolve(
    task: str,
    provider: str | None,
    registry: ProviderRegistry,
    routes: dict[str, str],
) -> Any:
    if provider:
        if provider not in registry:
            msg = f"Provider '{provider}' not in registry for task '{task}'. Available: {list(registry.list())}"
            raise RuntimeError(msg)
        return registry.get(provider)
    name = routes.get(task) or registry.default_name
    if name is None:
        msg = f"No provider available for task '{task}'. Register a provider first via registry.register()."
        raise RuntimeError(msg)
    if name not in registry:
        name = registry.default_name
    if name is None:
        msg = (
            f"No provider available for task '{task}'. "
            f"Route resolved to an unregistered provider and no fallback default is set. "
            f"Available: {list(registry.list())}"
        )
        raise RuntimeError(msg)
    return registry.get(name)


def resolve_name(
    task: str,
    provider: str | None,
    registry: ProviderRegistry,
    routes: dict[str, str],
) -> str:
    if provider:
        return provider
    name = routes.get(task) or registry.default_name
    if name and name not in registry:
        name = registry.default_name
    return name or "unknown"
