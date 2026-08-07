"""XxxProvider — implementación del contrato LLM vía Xxx API.

Xxx es API-compatible con OpenAI. Este provider hereda de OpenAIProvider
y fija el endpoint y modelos por defecto de Xxx.

Configuración vía motor.core.secrets:
    XXX_API_KEY — requerido
    XXX_MODEL — default: default-model
    XXX_TIMEOUT — default: 60
    XXX_TEMPERATURE — default: 0.3
    XXX_MAX_TOKENS — default: 4096
"""

from __future__ import annotations

import logging
from typing import Any

from motor.core.llm.openai import OpenAIProvider
from motor.core.secrets import get_secret

log = logging.getLogger(__name__)


class XxxProvider(OpenAIProvider):
    """Proveedor LLM que conecta con Xxx vía API OpenAI-compatible."""

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
        self._provider_name = "xxx"
        self._api_key = get_secret("XXX_API_KEY")
        self._base_url = "https://api.xxx.com/openai/v1"
        self._model = get_secret("XXX_MODEL", "default-model")
        self._embedding_model = ""
        self._timeout = int(get_secret("XXX_TIMEOUT", "60"))
        self._temperature = float(get_secret("XXX_TEMPERATURE", "0.3"))
        self._max_tokens = int(get_secret("XXX_MAX_TOKENS", "4096"))

    def embed(self, texts, model=None):
        log.warning("Xxx no soporta embeddings nativos")
        return [[0.0] * 768 for _ in texts]

    async def embed_async(self, texts, model=None):
        log.warning("Xxx no soporta embeddings nativos")
        return [[0.0] * 768 for _ in texts]


# Ver docs/LLM_PROVIDER_TEMPLATE.md completo en el repo
