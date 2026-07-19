"""Registry de proveedores LLM.

Gestiona el ciclo de vida de los proveedores registrados.

Uso:
    from motor.core.llm.registry import registry

    registry.register("ollama", OllamaProvider())
    registry.register("openai", OpenAIProvider())

    provider = registry.get("ollama")
    provider.generate("Hello")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.llm.base import BaseLLMProvider


class ProviderRegistry:
    """Registro de proveedores LLM. Thread-safe por naturaleza (dict operations
    are atomic in CPython para keys aislados).
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseLLMProvider] = {}
        self._default_name: str | None = None

    def register(self, name: str, provider: BaseLLMProvider, *, default: bool = False) -> None:
        """Registra un proveedor. Si default=True, se establece como predeterminado."""
        self._providers[name] = provider
        if default or self._default_name is None:
            self._default_name = name

    def unregister(self, name: str) -> None:
        """Elimina un proveedor del registro. Si era el default, se actualiza."""
        self._providers.pop(name, None)
        if self._default_name == name:
            restantes = list(self._providers)
            self._default_name = restantes[0] if restantes else None

    def get(self, name: str) -> BaseLLMProvider:
        """Obtiene un proveedor por nombre. Lanza KeyError si no existe."""
        return self._providers[name]

    def list(self) -> dict[str, type[BaseLLMProvider]]:
        """Devuelve un dict nombre -> clase de los proveedores registrados."""
        return {k: type(v) for k, v in self._providers.items()}

    @property
    def default(self) -> BaseLLMProvider | None:
        """Devuelve el proveedor predeterminado, o None si no hay ninguno."""
        if self._default_name is None:
            return None
        return self._providers.get(self._default_name)

    @property
    def default_name(self) -> str | None:
        """Nombre del proveedor predeterminado."""
        return self._default_name

    def __contains__(self, name: str) -> bool:
        return name in self._providers

    def __len__(self) -> int:
        return len(self._providers)


# Singleton global
registry = ProviderRegistry()
