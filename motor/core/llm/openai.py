"""OpenAIProvider — implementación del contrato LLM vía OpenAI-compatible API.

Soporta cualquier API compatible con OpenAI (OpenAI, Groq, DeepSeek,
OpenRouter, etc.) mediante configuración de endpoint y API key.

Configuración:
    Los secretos se obtienen vía motor.core.secrets.
    Requiere: OPENAI_API_KEY (variable de entorno o /etc/ura/secrets.env)

    Opcional:
        OPENAI_BASE_URL  — endpoint base (default: https://api.openai.com/v1)
        OPENAI_MODEL     — modelo por defecto (default: gpt-4o-mini)
        OPENAI_EMBEDDING_MODEL — modelo de embeddings (default: text-embedding-3-small)
        OPENAI_TIMEOUT   — timeout en segundos (default: 120)
        OPENAI_TEMPERATURE — temperatura (default: 0.3)
        OPENAI_MAX_TOKENS — tokens máximos (default: 1024)
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from motor.core.llm._logging import log_call
from motor.core.llm.base import BaseLLMProvider
from motor.core.secrets import get_secret

log = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """Proveedor LLM compatible con OpenAI API."""

    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "chat": True,
            "embeddings": True,
            "streaming": True,
            "tools": True,
            "json_mode": True,
            "multimodal": True,
            "vision": True,
            "max_context": 128000,
            "max_output": 16384,
        }

    def __init__(self) -> None:
        self._provider_name = "openai"
        self._api_key = get_secret("OPENAI_API_KEY")
        self._base_url = get_secret("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self._model: str = get_secret("OPENAI_MODEL", "gpt-4o-mini")
        self._embedding_model: str = get_secret("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self._timeout: int = int(get_secret("OPENAI_TIMEOUT", "120"))
        self._temperature: float = float(get_secret("OPENAI_TEMPERATURE", "0.3"))
        self._max_tokens: int = int(get_secret("OPENAI_MAX_TOKENS", "1024"))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

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
        model_name = model or self._embedding_model
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
            log_call(
                self._provider_name,
                model_name,
                latency_ms,
                batch_size=len(texts),
                vectors=len(embeddings),
            )
            return embeddings
        except Exception:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "embed_error")
            if model_name == self._embedding_model:
                log.warning("OpenAI embed falló, reintentando uno por uno")
            resultados: list[list[float]] = []
            for t in texts:
                try:
                    r = httpx.post(
                        f"{self._base_url}/embeddings",
                        headers=self._headers(),
                        json={"model": model_name, "input": t},
                        timeout=self._timeout,
                    )
                    r.raise_for_status()
                    resultados.append(r.json()["data"][0]["embedding"])
                except Exception:
                    log.warning("error generando embedding individual, continuando")
                    resultados.append([0.0] * 1536)
            return resultados

    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model_name = model or self._embedding_model
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                r = await client.post(
                    f"{self._base_url}/embeddings",
                    headers=self._headers(),
                    json={"model": model_name, "input": texts},
                )
                r.raise_for_status()
                data = r.json()
                embeddings = [item["embedding"] for item in data["data"]]
                latency_ms = (time.monotonic() - t0) * 1000
                log_call(
                    self._provider_name,
                    model_name,
                    latency_ms,
                    async_=True,
                    batch_size=len(texts),
                    vectors=len(embeddings),
                )
                return embeddings
        except Exception:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "embed_error", async_=True)
            log.warning("OpenAI embed_async batch falló, reintentando individual")
            resultados: list[list[float]] = []
            for t in texts:
                try:
                    async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                        r = await client.post(
                            f"{self._base_url}/embeddings",
                            headers=self._headers(),
                            json={"model": model_name, "input": t},
                        )
                        r.raise_for_status()
                        resultados.append(r.json()["data"][0]["embedding"])
                except Exception:
                    log.warning("error generando embedding async individual, continuando")
                    resultados.append([0.0] * 1536)
            return resultados

    def health(self) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            r = httpx.get(
                f"{self._base_url}/models",
                headers=self._headers(),
                timeout=5,
            )
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
