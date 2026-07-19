"""LMStudioProvider — implementación del contrato LLM vía LM Studio API.

LM Studio expone una API compatible con OpenAI en localhost.

Configuración mediante secretos:
    LMSTUDIO_BASE_URL    — opcional (default: http://localhost:1234/v1)
    LMSTUDIO_MODEL       — opcional (default: local-model)
    LMSTUDIO_TIMEOUT     — opcional (default: 120)
    LMSTUDIO_TEMPERATURE — opcional (default: 0.3)
    LMSTUDIO_MAX_TOKENS  — opcional (default: 1024)
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from motor.core.llm._logging import log_call
from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION, BaseLLMProvider
from motor.core.secrets import get_secret

log = logging.getLogger(__name__)


class LMStudioProvider(BaseLLMProvider):
    """Proveedor LLM que conecta con LM Studio (OpenAI-compatible local)."""

    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "chat": True,
            "embeddings": True,
            "streaming": True,
            "tools": False,
            "json_mode": True,
            "multimodal": False,
            "vision": False,
            "max_context": 8192,
            "max_output": 2048,
        }

    def __init__(self) -> None:
        self._provider_name = "lmstudio"
        self._base_url = get_secret(
            "LMSTUDIO_BASE_URL",
            "http://localhost:1234/v1",
        ).rstrip("/")
        self._model: str = get_secret("LMSTUDIO_MODEL", "local-model")
        self._timeout: int = int(get_secret("LMSTUDIO_TIMEOUT", "120"))
        self._temperature: float = float(get_secret("LMSTUDIO_TEMPERATURE", "0.3"))
        self._max_tokens: int = int(get_secret("LMSTUDIO_MAX_TOKENS", "1024"))

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
        opts = dict(options or {})
        opts.setdefault("temperature", self._temperature)
        opts.setdefault("max_tokens", self._max_tokens)
        model_name = model or self._model
        t0 = time.monotonic()
        try:
            r = httpx.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    **opts,
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            respuesta = data["choices"][0]["message"]["content"].strip()
            latency_ms = (time.monotonic() - t0) * 1000
            usage = data.get("usage", {})
            log_call(
                self._provider_name,
                model_name,
                latency_ms,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
            return respuesta
        except httpx.TimeoutException:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "timeout")
            return "Error: La generación excedió el tiempo de espera."
        except httpx.HTTPStatusError as e:
            latency_ms = (time.monotonic() - t0) * 1000
            error = f"http_{e.response.status_code}"
            log_call(self._provider_name, model_name, latency_ms, error)
            return f"Error: El servicio respondió con código {e.response.status_code}."
        except httpx.RequestError:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "connection_error")
            return "Error: No se pudo conectar con el servicio."
        except Exception:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "unexpected")
            log.warning("error inesperado en generate")
            return "Error: Error interno del proveedor."

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model_name = model or self._model
        t0 = time.monotonic()
        try:
            r = httpx.post(
                f"{self._base_url}/embeddings",
                headers=self._headers(),
                json={"model": model_name, "input": texts},
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            embeddings = [item["embedding"] for item in data["data"]]
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, batch_size=len(texts), vectors=len(embeddings))
            return embeddings
        except Exception:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "embed_error")
            return [[0.0] * FALLBACK_EMBEDDING_DIMENSION for _ in texts]

    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        import asyncio

        return await asyncio.to_thread(self.embed, texts, model)

    def health(self) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            r = httpx.get(f"{self._base_url}/models", timeout=5)
            latency_ms = (time.monotonic() - t0) * 1000
            if r.is_error:
                log_call(self._provider_name, "health", latency_ms, f"http_{r.status_code}")
                return {
                    "provider": self._provider_name,
                    "status": "error",
                    "detail": r.text[:200],
                    "latency_ms": latency_ms,
                }
            modelos = r.json().get("data", [])
            log_call(self._provider_name, "health", latency_ms, modelos_disponibles=len(modelos))
            return {
                "provider": self._provider_name,
                "status": "ok",
                "modelos_disponibles": [m["id"] for m in modelos],
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, "health", latency_ms, "health_error")
            return {"provider": self._provider_name, "status": "error", "detail": str(e), "latency_ms": latency_ms}
