"""OllamaProvider — implementación del contrato LLM vía Ollama API.

Configuración unificada vía CONFIG:
    llm.model -> modelo por defecto
    llm.embedding_model -> modelo de embeddings
    llm.timeout / rag.timeout -> timeout general
    llm.temperature / rag.temperature -> temperatura
    llm.max_tokens / rag.max_tokens -> tokens máximos
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from core.config_manager import CONFIG, get_ollama_url
from motor.core.llm._logging import log_call
from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION, BaseLLMProvider
from motor.core.secrets import get_secret

log = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Proveedor LLM que conecta con Ollama vía API HTTP."""

    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "chat": True,
            "embeddings": True,
            "streaming": True,
            "tools": True,
            "json_mode": True,
            "multimodal": False,
            "vision": True,
            "max_context": 32768,
            "max_output": 4096,
        }

    def __init__(self) -> None:
        self._provider_name = "ollama"
        _cfg = CONFIG.get("llm", {})
        self._url = get_ollama_url()
        self._rag_model: str = (
            _cfg.get("model") or CONFIG.get("fallback_model") or get_secret("OLLAMA_MODEL") or "qwen2.5:3b"
        )
        self._embedding_model: str = (
            _cfg.get("embedding_model") or get_secret("OLLAMA_EMBEDDING_MODEL") or "nomic-embed-text"
        )
        self._timeout: int = int(
            _cfg.get("timeout") or CONFIG.get("rag", {}).get("timeout") or get_secret("OLLAMA_TIMEOUT") or "120",
        )
        self._temperature: float = float(
            _cfg.get("temperature")
            or CONFIG.get("rag", {}).get("temperature")
            or get_secret("OLLAMA_TEMPERATURE")
            or "0.3",
        )
        self._max_tokens: int = int(
            _cfg.get("max_tokens")
            or CONFIG.get("rag", {}).get("max_tokens")
            or get_secret("OLLAMA_MAX_TOKENS")
            or "1024",
        )

    def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
        opts = dict(options or {})
        opts.setdefault("temperature", self._temperature)
        opts.setdefault("num_predict", self._max_tokens)
        model_name = model or self._rag_model
        t0 = time.monotonic()
        error: str | None = None
        try:
            r = httpx.post(
                f"{self._url}/api/generate",
                json={"model": model_name, "prompt": prompt, "stream": False, "options": opts},
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            respuesta = data.get("response", "").strip()
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(
                self._provider_name,
                model_name,
                latency_ms,
                eval_count=data.get("eval_count", 0),
                eval_duration_ms=data.get("eval_duration", 0) / 1e6 if data.get("eval_duration") else 0,
            )
            return respuesta or "El modelo no generó ninguna respuesta."
        except httpx.TimeoutException:
            latency_ms = (time.monotonic() - t0) * 1000
            error = "timeout"
            log_call(self._provider_name, model_name, latency_ms, error)
            return "Error: La generación excedió el tiempo de espera."
        except httpx.HTTPStatusError as e:
            latency_ms = (time.monotonic() - t0) * 1000
            error = f"http_{e.response.status_code}"
            log_call(self._provider_name, model_name, latency_ms, error)
            return f"Error: El servicio de generación respondió con código {e.response.status_code}."
        except httpx.RequestError:
            latency_ms = (time.monotonic() - t0) * 1000
            error = "connection_error"
            log_call(self._provider_name, model_name, latency_ms, error)
            return "Error: No se pudo conectar con el servicio de generación."
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
                f"{self._url}/api/embed",
                json={"model": model_name, "input": texts},
                timeout=self._timeout,
            )
            if r.status_code == 200:
                latency_ms = (time.monotonic() - t0) * 1000
                result = r.json()["embeddings"]
                log_call(self._provider_name, model_name, latency_ms, batch_size=len(texts), vectors=len(result))
                return result
        except httpx.RequestError:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "request_error")
            log.warning("Ollama /api/embed batch falló, intentando individual")
        except Exception:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "unexpected")
            log.warning("Ollama /api/embed batch falló (except), intentando individual")

        resultados: list[list[float]] = []
        for t in texts:
            try:
                r = httpx.post(
                    f"{self._url}/api/embeddings",
                    json={"model": model_name, "prompt": t},
                    timeout=self._timeout,
                )
                r.raise_for_status()
                resultados.append(r.json()["embedding"])
            except Exception:
                log.warning("error generando embedding (old API), continuando")
                resultados.append([0.0] * FALLBACK_EMBEDDING_DIMENSION)
        return resultados

    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model_name = model or self._embedding_model
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                r = await client.post(
                    f"{self._url}/api/embed",
                    json={"model": model_name, "input": texts},
                )
                if r.status_code == 200:
                    latency_ms = (time.monotonic() - t0) * 1000
                    result = r.json()["embeddings"]
                    log_call(
                        self._provider_name,
                        model_name,
                        latency_ms,
                        async_=True,
                        batch_size=len(texts),
                        vectors=len(result),
                    )
                    return result
        except httpx.RequestError:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "request_error", async_=True)
            log.warning("Ollama /api/embed async batch falló, intentando individual")
        except Exception:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, model_name, latency_ms, "unexpected", async_=True)
            log.warning("Ollama /api/embed async batch falló (except), intentando individual")

        resultados: list[list[float]] = []
        for t in texts:
            try:
                async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                    r = await client.post(
                        f"{self._url}/api/embeddings",
                        json={"model": model_name, "prompt": t},
                    )
                    r.raise_for_status()
                    resultados.append(r.json()["embedding"])
            except Exception:
                log.warning("error generando embedding async (old API), continuando")
                resultados.append([0.0] * FALLBACK_EMBEDDING_DIMENSION)
        return resultados

    def health(self) -> dict[str, Any]:
        t0 = time.monotonic()
        error: str | None = None
        try:
            r = httpx.get(f"{self._url}/api/tags", timeout=5)
            latency_ms = (time.monotonic() - t0) * 1000
            if r.is_error:
                error = f"http_{r.status_code}"
                log_call(self._provider_name, "health", latency_ms, error)
                return {
                    "provider": self._provider_name,
                    "status": "error",
                    "detail": r.text[:200],
                    "latency_ms": latency_ms,
                }
            modelos = r.json().get("models", [])
            log_call(self._provider_name, "health", latency_ms, modelos_disponibles=len(modelos))
            return {
                "provider": self._provider_name,
                "status": "ok",
                "modelos_disponibles": [m["name"] for m in modelos],
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, "health", latency_ms, "health_error")
            return {"provider": self._provider_name, "status": "error", "detail": str(e), "latency_ms": latency_ms}
