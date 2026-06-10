import json
import os
from typing import AsyncGenerator

import httpx

from .base import Provider, ProviderError

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_TIMEOUT = int(os.environ.get("MOCHILA_OLLAMA_TIMEOUT", "180"))


class OllamaProvider(Provider):
    @property
    def nombre(self) -> str:
        return "ollama"

    @property
    def timeout(self) -> int:
        return OLLAMA_TIMEOUT

    async def chat(
        self,
        modelo: str,
        mensajes: list,
        stream: bool = False,
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncGenerator[dict, None]:
        payload = {
            "model": modelo,
            "messages": mensajes,
            "stream": stream,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
            if stream:
                async with client.stream(
                    "POST", f"{OLLAMA_BASE}/api/chat", json=payload
                ) as resp:
                    if resp.is_error:
                        text = await resp.aread()
                        raise ProviderError(
                            f"Ollama error: {resp.status_code} {text.decode(errors='replace')[:200]}",
                            provider=self.nombre,
                            status_code=resp.status_code,
                        )
                    async for line in resp.aiter_lines():
                        if line.strip():
                            chunk = json.loads(line)
                            yield self._to_openai_chunk(chunk, modelo)
                    return

            resp = await client.post(
                f"{OLLAMA_BASE}/api/chat", json=payload
            )
            if resp.is_error:
                raise ProviderError(
                    f"Ollama error: {resp.status_code} {resp.text[:200]}",
                    provider=self.nombre,
                    status_code=resp.status_code,
                )
            yield self._to_openai(resp.json(), modelo)

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{OLLAMA_BASE}/api/tags")
                if resp.is_error:
                    return {"status": "error", "detail": resp.text[:100]}
                modelos = resp.json().get("models", [])
                return {
                    "status": "ok",
                    "modelos_disponibles": [m["name"] for m in modelos],
                    "latencia_ms": resp.elapsed.total_seconds() * 1000,
                }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    @staticmethod
    def _to_openai_chunk(chunk: dict, modelo: str) -> dict:
        done = chunk.get("done", False)
        delta = {}
        if "message" in chunk:
            msg = chunk["message"]
            if msg.get("content"):
                delta["content"] = msg["content"]
            if msg.get("role"):
                delta["role"] = msg["role"]
        if not delta and not done:
            return {}
        return {
            "id": chunk.get("id", "ollama-unknown"),
            "object": "chat.completion.chunk",
            "created": chunk.get("created_at", ""),
            "model": modelo,
            "choices": [{"index": 0, "delta": delta, "finish_reason": "stop" if done else None}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            if done
            else None,
        }

    @staticmethod
    def _to_openai(data: dict, modelo: str) -> dict:
        msg = data.get("message", {})
        return {
            "id": data.get("id", "ollama-unknown"),
            "object": "chat.completion",
            "created": data.get("created_at", ""),
            "model": modelo,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": msg.get("role", "assistant"),
                        "content": msg.get("content", ""),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": (data.get("prompt_eval_count", 0) + data.get("eval_count", 0)),
            },
        }
