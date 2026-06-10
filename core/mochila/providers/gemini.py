import os
from typing import AsyncGenerator

from .base import Provider, ProviderError


class GeminiProvider(Provider):
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")

    @property
    def nombre(self) -> str:
        return "gemini"

    @property
    def timeout(self) -> int:
        return 60

    async def chat(
        self,
        modelo: str,
        mensajes: list,
        stream: bool = False,
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncGenerator[dict, None]:
        if not self.api_key:
            raise ProviderError(
                "GEMINI_API_KEY no configurada",
                provider=self.nombre,
            )
        raise ProviderError(
            "Implementación pendiente",
            provider=self.nombre,
        )

    async def health(self) -> dict:
        if not self.api_key:
            return {"status": "no_configurado", "detail": "GEMINI_API_KEY no configurada"}
        return {"status": "ok", "detail": "API key presente, implementación pendiente"}
