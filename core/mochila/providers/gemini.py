import json
import os
from typing import AsyncGenerator

import httpx

from .base import Provider, ProviderError

GEMINI_BASE = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
GEMINI_TIMEOUT = int(os.environ.get("MOCHILA_GEMINI_TIMEOUT", "60"))


def _gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    cred_path = os.path.expanduser("~/.config/opencode/.credentials/gemini.json")
    try:
        with open(cred_path) as f:
            data = json.load(f)
            return data.get("api_key", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


class GeminiProvider(Provider):
    def __init__(self):
        self.api_key = _gemini_api_key()

    @property
    def nombre(self) -> str:
        return "gemini"

    @property
    def timeout(self) -> int:
        return GEMINI_TIMEOUT

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

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
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
                    f"{GEMINI_BASE}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.is_error:
                        text = await resp.aread()
                        raise ProviderError(
                            f"Gemini error: {resp.status_code} {text.decode(errors='replace')[:200]}",
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
                    f"{GEMINI_BASE}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.is_error:
                    raise ProviderError(
                        f"Gemini error: {resp.status_code} {resp.text[:200]}",
                        provider=self.nombre,
                        status_code=resp.status_code,
                    )
                yield resp.json()

    async def health(self) -> dict:
        if not self.api_key:
            return {"status": "no_configurado", "detail": "GEMINI_API_KEY no configurada"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{GEMINI_BASE}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.is_error:
                    return {"status": "error", "detail": resp.text[:100]}
                data = resp.json()
                modelos = data.get("data", [])
                return {
                    "status": "ok",
                    "modelos_disponibles": [m["id"].replace("models/", "") for m in modelos[:10]],
                    "total_modelos": len(modelos),
                    "latencia_ms": resp.elapsed.total_seconds() * 1000,
                }
        except Exception as e:
            return {"status": "error", "detail": str(e)}
