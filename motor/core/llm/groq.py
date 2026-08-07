"""GroqProvider — implementación del contrato LLM vía Groq API.

Groq es API-compatible con OpenAI. Este provider hereda de OpenAIProvider
y fija el endpoint y modelos por defecto de Groq.

Configuración vía motor.core.secrets:
    GROQ_API_KEY — requerido
    GROQ_MODEL — default: llama-3.1-70b-versatile
    GROQ_TIMEOUT — default: 60
    GROQ_TEMPERATURE — default: 0.3
    GROQ_MAX_TOKENS — default: 4096
"""

from __future__ import annotations

import logging
from typing import Any

from motor.core.llm.openai import OpenAIProvider
from motor.core.secrets import get_secret

log = logging.getLogger(__name__)


class GroqProvider(OpenAIProvider):
    """Proveedor LLM que conecta con Groq vía API OpenAI-compatible."""

    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "chat": True,
            "embeddings": False,
            "streaming": True,
            "tools": True,
            "json_mode": True,
            "multimodal": False,
            "vision": False,
            "max_context": 131072,
            "max_output": 4096,
        }

    def __init__(self) -> None:
        self._provider_name = "groq"
        self._api_key = get_secret("GROQ_API_KEY")
        self._base_url = "https://api.groq.com/openai/v1"
        self._model = get_secret("GROQ_MODEL", "llama-3.1-70b-versatile")
        self._embedding_model = ""
        self._timeout = int(get_secret("GROQ_TIMEOUT", "60"))
        self._temperature = float(get_secret("GROQ_TEMPERATURE", "0.3"))
        self._max_tokens = int(get_secret("GROQ_MAX_TOKENS", "4096"))

    def embed(self, texts, model=None):
        log.warning("Groq no soporta embeddings nativos")
        return [[0.0] * 768 for _ in texts]

    async def embed_async(self, texts, model=None):
        log.warning("Groq no soporta embeddings nativos")
        return [[0.0] * 768 for _ in texts]
