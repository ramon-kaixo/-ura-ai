"""GeminiProvider — implementación del contrato LLM vía Google Gemini API.

Configuración mediante secretos:
    GEMINI_API_KEY       — requerida
    GEMINI_MODEL         — opcional (default: gemini-2.0-flash-001)
    GEMINI_EMBEDDING_MODEL — opcional (default: text-embedding-004)
    GEMINI_TIMEOUT       — opcional (default: 120)
    GEMINI_TEMPERATURE   — opcional (default: 0.3)
    GEMINI_MAX_TOKENS    — opcional (default: 1024)
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from motor.core.llm.base import BaseLLMProvider
from motor.core.secrets import get_secret

log = logging.getLogger(__name__)


def _log_call(provider: str, model: str, latency_ms: float, error: str | None = None, **extra: Any) -> None:
    extra_str = " ".join(f"{k}={v}" for k, v in extra.items())
    msg = "llm_call  provider=%s model=%s latency_ms=%.0f error=%s %s"
    if error:
        log.warning(msg, provider, model, latency_ms, error, extra_str)
    else:
        log.info(msg, provider, model, latency_ms, "null", extra_str)


class GeminiProvider(BaseLLMProvider):
    """Proveedor LLM que conecta con Google Gemini API."""

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
            "max_context": 1048576,
            "max_output": 8192,
        }

    def __init__(self) -> None:
        self._provider_name = "gemini"
        self._api_key = get_secret("GEMINI_API_KEY")
        self._model: str = get_secret("GEMINI_MODEL", "gemini-2.0-flash-001")
        self._embedding_model: str = get_secret("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
        self._timeout: int = int(get_secret("GEMINI_TIMEOUT", "120"))
        self._temperature: float = float(get_secret("GEMINI_TEMPERATURE", "0.3"))
        self._max_tokens: int = int(get_secret("GEMINI_MAX_TOKENS", "1024"))

    def _base_url(self, model: str) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}"

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
        opts = dict(options or {})
        opts.setdefault("temperature", self._temperature)
        opts.setdefault("maxOutputTokens", self._max_tokens)
        model_name = model or self._model
        t0 = time.monotonic()
        try:
            url = f"{self._base_url(model_name)}:generateContent?key={self._api_key}"
            r = httpx.post(
                url,
                headers=self._headers(),
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": opts,
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            candidates = data.get("candidates", [])
            respuesta = ""
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                for part in parts:
                    respuesta += part.get("text", "")
            respuesta = respuesta.strip()
            latency_ms = (time.monotonic() - t0) * 1000
            usage = data.get("usageMetadata", {})
            _log_call(
                self._provider_name, model_name, latency_ms,
                prompt_tokens=usage.get("promptTokenCount"),
                candidates_tokens=usage.get("candidatesTokenCount"),
            )
            return respuesta or "El modelo no generó ninguna respuesta."
        except httpx.TimeoutException:
            latency_ms = (time.monotonic() - t0) * 1000
            _log_call(self._provider_name, model_name, latency_ms, "timeout")
            return "Error: La generación excedió el tiempo de espera."
        except httpx.HTTPStatusError as e:
            latency_ms = (time.monotonic() - t0) * 1000
            error = f"http_{e.response.status_code}"
            _log_call(self._provider_name, model_name, latency_ms, error)
            return f"Error: El servicio respondió con código {e.response.status_code}."
        except httpx.RequestError:
            latency_ms = (time.monotonic() - t0) * 1000
            _log_call(self._provider_name, model_name, latency_ms, "connection_error")
            return "Error: No se pudo conectar con el servicio."
        except Exception:
            latency_ms = (time.monotonic() - t0) * 1000
            _log_call(self._provider_name, model_name, latency_ms, "unexpected")
            log.warning("error inesperado en generate")
            return "Error: Error interno del proveedor."

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model_name = model or self._embedding_model
        t0 = time.monotonic()
        try:
            url = f"{self._base_url(model_name)}:batchEmbedContents?key={self._api_key}"
            r = httpx.post(
                url,
                headers=self._headers(),
                json={
                    "requests": [
                        {"model": f"models/{model_name}", "content": {"parts": [{"text": t}]}}
                        for t in texts
                    ],
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            embeddings = [e["values"] for e in data.get("embeddings", [])]
            latency_ms = (time.monotonic() - t0) * 1000
            _log_call(self._provider_name, model_name, latency_ms, batch_size=len(texts), vectors=len(embeddings))
            return embeddings
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            _log_call(self._provider_name, model_name, latency_ms, str(e))
            return [[0.0] * 768 for _ in texts]

    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        import asyncio
        return await asyncio.to_thread(self.embed, texts, model)

    def health(self) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            model_name = self._model
            url = f"{self._base_url(model_name)}?key={self._api_key}"
            r = httpx.get(url, headers=self._headers(), timeout=5)
            latency_ms = (time.monotonic() - t0) * 1000
            if r.is_error:
                _log_call(self._provider_name, "health", latency_ms, f"http_{r.status_code}")
                return {
                    "provider": self._provider_name, "status": "error",
                    "detail": r.text[:200], "latency_ms": latency_ms,
                }
            _log_call(self._provider_name, "health", latency_ms)
            return {
                "provider": self._provider_name,
                "status": "ok",
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            _log_call(self._provider_name, "health", latency_ms, "health_error")
            return {"provider": self._provider_name, "status": "error", "detail": str(e), "latency_ms": latency_ms}
