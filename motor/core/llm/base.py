"""BaseLLMProvider — contrato abstracto para proveedores LLM.

Todos los proveedores deben implementar esta interfaz.
La API pública de motor.core.llm (generate, embed, embed_async, health)
delega en una instancia por defecto.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Contrato abstracto para proveedores de lenguaje."""

    @abstractmethod
    def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
        ...

    @abstractmethod
    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        ...

    @abstractmethod
    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        ...
