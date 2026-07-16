"""LLM — Cliente de inferencia unificado.

Exporta solo comportamiento:
    generate(prompt, model, options) -> str
    embed(texts, model) -> list[list[float]]
    embed_async(texts, model) -> list[list[float]]
    health() -> dict

El proveedor por defecto se selecciona según CONFIG["llm"]["provider"].
Por defecto es OllamaProvider. La selección de proveedor también puede
realizarse mediante router + registry (ver F18).
"""

import logging

from motor.core.llm.ollama import OllamaProvider
from motor.core.llm.registry import registry

log = logging.getLogger(__name__)

try:
    from core.config_manager import CONFIG

    provider_name = CONFIG.get("llm", {}).get("provider", "ollama")
except Exception:
    provider_name = "ollama"

_default: OllamaProvider

if provider_name == "openai":
    from motor.core.llm.openai import OpenAIProvider

    _default = OpenAIProvider()
    registry.register("openai", _default, default=True)
    registry.register("ollama", OllamaProvider())
    log.info("LLM provider set to openai (from config)")
else:
    _default = OllamaProvider()
    registry.register("ollama", _default, default=True)
    try:
        from motor.core.llm.openai import OpenAIProvider

        registry.register("openai", OpenAIProvider())
    except Exception as exc:
        log.info("OpenAI provider not available: %s", exc)

generate = _default.generate
embed = _default.embed
embed_async = _default.embed_async
health = _default.health

__all__ = ["embed", "embed_async", "generate", "health"]
