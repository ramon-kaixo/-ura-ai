"""AnthropicProvider — implementación del contrato LLM vía Anthropic API.

Soporta Anthropic Claude API (messages endpoint).
Configuración mediante secretos:
    ANTHROPIC_API_KEY  — requerida
    ANTHROPIC_BASE_URL — opcional (default: https://api.anthropic.com/v1)
    ANTHROPIC_MODEL    — opcional (default: claude-sonnet-4-20250514)
    ANTHROPIC_TIMEOUT  — opcional (default: 120)
    ANTHROPIC_TEMPERATURE — opcional (default: 0.3)
    ANTHROPIC_MAX_TOKENS  — opcional (default: 1024)
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



class AnthropicProvider(BaseLLMProvider):
    """Proveedor LLM que conecta con Anthropic Claude API."""

    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "chat": True,
            "embeddings": False,
            "streaming": True,
            "tools": True,
            "json_mode": True,
            "multimodal": True,
            "vision": True,
            "max_context": 200000,
            "max_output": 8192,
        }

    def __init__(self) -> None:
        self._provider_name = "anthropic"
        self._api_key = get_secret("ANTHROPIC_API_KEY")
        self._base_url = get_secret(
            "ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1",
        ).rstrip("/")
        self._model: str = get_secret("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        self._timeout: int = int(get_secret("ANTHROPIC_TIMEOUT", "120"))
        self._temperature: float = float(get_secret("ANTHROPIC_TEMPERATURE", "0.3"))
        self._max_tokens: int = int(get_secret("ANTHROPIC_MAX_TOKENS", "1024"))

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
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
                f"{self._base_url}/messages",
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
            content = data.get("content", [])
            respuesta = ""
            for block in content:
                if block.get("type") == "text":
                    respuesta += block.get("text", "")
            respuesta = respuesta.strip()
            latency_ms = (time.monotonic() - t0) * 1000
            usage = data.get("usage", {})
            log_call(
                self._provider_name, model_name, latency_ms,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            )
            return respuesta or "El modelo no generó ninguna respuesta."
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
        """Anthropic no ofrece embeddings nativos. Retorna degradación controlada."""
        log_call(self._provider_name, model or "none", 0, "embeddings_not_supported")
        return [[0.0] * FALLBACK_EMBEDDING_DIMENSION for _ in texts]

    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        log_call(self._provider_name, model or "none", 0, "embeddings_not_supported", async_=True)
        return [[0.0] * FALLBACK_EMBEDDING_DIMENSION for _ in texts]

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
                    "provider": self._provider_name, "status": "error",
                    "detail": r.text[:200], "latency_ms": latency_ms,
                }
            modelos = r.json().get("data", [])
            log_call(self._provider_name, "health", latency_ms, modelos_disponibles=len(modelos))
            return {
                "provider": self._provider_name,
                "status": "ok",
                "modelos_disponibles": [m.get("id") for m in modelos],
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            log_call(self._provider_name, "health", latency_ms, "health_error")
            return {"provider": self._provider_name, "status": "error", "detail": str(e), "latency_ms": latency_ms}
