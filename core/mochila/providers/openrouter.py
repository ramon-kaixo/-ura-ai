import json
import os
from collections.abc import AsyncGenerator

import httpx

from .base import Provider, ProviderError

OPENROUTER_BASE = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_TIMEOUT = int(os.environ.get("MOCHILA_OPENROUTER_TIMEOUT", "60"))


class OpenRouterProvider(Provider):
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")

    @property
    def nombre(self) -> str:
        return "openrouter"

    @property
    def timeout(self) -> int:
        return OPENROUTER_TIMEOUT

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
                "OPENROUTER_API_KEY no configurada",
                provider=self.nombre,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "https://openrouter.ai/"),
        }
        payload = {
            "model": modelo,
            "messages": mensajes,
            "stream": stream,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
            if stream:
                async with client.stream(
                    "POST",
                    f"{OPENROUTER_BASE}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.is_error:
                        text = await resp.aread()
                        raise ProviderError(
                            f"OpenRouter error: {resp.status_code} {text.decode(errors='replace')[:200]}",
                            provider=self.nombre,
                            status_code=resp.status_code,
                        )
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:].strip()
                            if data == "[DONE]":
                                yield {
                                    "choices": [{"delta": {}, "finish_reason": "stop"}],
                                    "usage": None,
                                }
                                return
                            if data:
                                yield json.loads(data)
            else:
                resp = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.is_error:
                    raise ProviderError(
                        f"OpenRouter error: {resp.status_code} {resp.text[:200]}",
                        provider=self.nombre,
                        status_code=resp.status_code,
                    )
                yield resp.json()

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{OPENROUTER_BASE}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.is_error:
                    return {"status": "error", "detail": resp.text[:100]}
                data = resp.json()
                modelos = data.get("data", [])
                return {
                    "status": "ok",
                    "modelos_disponibles": [m["id"] for m in modelos[:20]],
                    "total_modelos": len(modelos),
                    "latencia_ms": resp.elapsed.total_seconds() * 1000,
                }
        except Exception as e:
            return {"status": "error", "detail": str(e)}
