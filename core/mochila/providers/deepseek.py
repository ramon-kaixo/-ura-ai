import json
import os
from collections.abc import AsyncGenerator

import httpx

from motor.core.secrets import get_secret
from motor.core.state import DegradedMode

from .base import Provider, ProviderError

DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_TIMEOUT = int(os.environ.get("MOCHILA_DEEPSEEK_TIMEOUT", "60"))


class DeepSeekProvider(Provider):
    def __init__(self) -> None:
        self.api_key = get_secret("DEEPSEEK_API_KEY", "")

    @property
    def nombre(self) -> str:
        return "deepseek"

    @property
    def timeout(self) -> int:
        return DEEPSEEK_TIMEOUT

    async def chat(
        self,
        modelo: str,
        mensajes: list,
        stream: bool = False,  # noqa: FBT001, FBT002
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncGenerator[dict, None]:
        if not self.api_key:
            msg = "DEEPSEEK_API_KEY no configurada"
            raise ProviderError(msg, provider=self.nombre)

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
                    f"{DEEPSEEK_BASE}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.is_error:
                        text = await resp.aread()
                        msg = f"DeepSeek error: {resp.status_code} {text.decode(errors='replace')[:200]}"
                        raise ProviderError(
                            msg,
                            provider=self.nombre,
                            status_code=resp.status_code,
                        )
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:].strip()
                            if data == "[DONE]":
                                yield {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": None}
                                return
                            if data:
                                yield json.loads(data)
            else:
                resp = await client.post(f"{DEEPSEEK_BASE}/chat/completions", json=payload, headers=headers)
                if resp.is_error:
                    msg = f"DeepSeek error: {resp.status_code} {resp.text[:200]}"
                    raise ProviderError(
                        msg,
                        provider=self.nombre,
                        status_code=resp.status_code,
                    )
                yield resp.json()

    async def health(self) -> dict:
        dm = DegradedMode.instancia()
        if not self.api_key:
            dm.mark_degraded("deepseek_provider")
            return {"status": "no_configurado", "detail": "DEEPSEEK_API_KEY no configurada"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{DEEPSEEK_BASE}/models", headers={"Authorization": f"Bearer {self.api_key}"})
                if resp.is_error:
                    dm.mark_degraded("deepseek_provider")
                    return {"status": "error", "detail": resp.text[:100]}
                data = resp.json()
                modelos = data.get("data", [])
                dm.mark_healthy("deepseek_provider")
                return {
                    "status": "ok",
                    "modelos_disponibles": [m["id"] for m in modelos[:10]],
                    "total_modelos": len(modelos),
                    "latencia_ms": resp.elapsed.total_seconds() * 1000,
                }
        except Exception as e:
            dm.mark_degraded("deepseek_provider")
            return {"status": "error", "detail": str(e)}
