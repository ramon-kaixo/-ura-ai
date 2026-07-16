"""Router de proveedores LLM.

Selecciona el proveedor adecuado según el tipo de tarea y delega la llamada.

Uso:
    router = LLMRouter(registry)
    respuesta = router.generate("Hola", model="qwen3:32b-q8_0")
    embeds = router.embed(["texto"])
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.core.llm.registry import ProviderRegistry

log = logging.getLogger(__name__)

# Mapa por defecto de tarea -> proveedor
DEFAULT_ROUTES: dict[str, str] = {
    "generate": "ollama",
    "embed": "ollama",
    "health": "ollama",
}


class LLMRouter:
    """Enruta peticiones LLM al proveedor adecuado.

    Sin lógica de negocio. Solo selecciona proveedor y delega.
    """

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        routes: dict[str, str] | None = None,
    ) -> None:
        from motor.core.llm.registry import ProviderRegistry as PR, registry as default_registry

        if registry is not None and not isinstance(registry, PR):
            raise TypeError(
                f"LLMRouter expected ProviderRegistry, got {type(registry).__name__}"
            )
        self._registry = default_registry if registry is None else registry
        self._routes = {**DEFAULT_ROUTES, **(routes or {})}

    @property
    def registry(self) -> ProviderRegistry:
        return self._registry

    def _resolve(self, task: str, provider: str | None) -> Any:
        """Resuelve el proveedor para una tarea."""
        if provider:
            if provider not in self._registry:
                raise RuntimeError(
                    f"Provider '{provider}' not in registry for task "
                    f"'{task}'. Available: {list(self._registry.list())}"
                )
            return self._registry.get(provider)
        name = self._routes.get(task) or self._registry.default_name
        if name is None:
            raise RuntimeError(
                f"No provider available for task '{task}'. "
                "Register a provider first via registry.register()."
            )
        if name not in self._registry:
            name = self._registry.default_name
        if name is None:
            raise RuntimeError(
                f"No provider available for task '{task}'. "
                "Route resolved to an unregistered provider "
                f"and no fallback default is set. "
                f"Available: {list(self._registry.list())}"
            )
        return self._registry.get(name)

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        options: dict | None = None,
        *,
        provider: str | None = None,
    ) -> str:
        """Genera texto usando el proveedor indicado."""
        prov = self._resolve("generate", provider)
        return prov.generate(prompt, model=model, options=options)

    def embed(
        self,
        texts: list[str],
        model: str | None = None,
        *,
        provider: str | None = None,
    ) -> list[list[float]]:
        """Genera embeddings usando el proveedor indicado."""
        prov = self._resolve("embed", provider)
        return prov.embed(texts, model=model)

    async def embed_async(
        self,
        texts: list[str],
        model: str | None = None,
        *,
        provider: str | None = None,
    ) -> list[list[float]]:
        """Genera embeddings asíncronos usando el proveedor indicado."""
        prov = self._resolve("embed", provider)
        return await prov.embed_async(texts, model=model)

    def health(self, *, provider: str | None = None) -> dict[str, Any]:
        """Health check del proveedor indicado."""
        prov = self._resolve("health", provider)
        return prov.health()
