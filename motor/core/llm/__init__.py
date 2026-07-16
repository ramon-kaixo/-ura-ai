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
from typing import Any

from motor.core.llm.ollama import OllamaProvider
from motor.core.llm.registry import registry


def _get_optional_providers() -> list[tuple[Any, str]]:
    """Retorna lista de (provider_class, provider_name) para registro opcional."""
    providers: list[tuple[Any, str]] = []
    try:
        from motor.core.llm.openai import OpenAIProvider

        providers.append((OpenAIProvider, "openai"))
    except Exception:  # noqa: S110
        pass
    try:
        from motor.core.llm.anthropic import AnthropicProvider

        providers.append((AnthropicProvider, "anthropic"))
    except Exception:  # noqa: S110
        pass
    try:
        from motor.core.llm.gemini import GeminiProvider

        providers.append((GeminiProvider, "gemini"))
    except Exception:  # noqa: S110
        pass
    try:
        from motor.core.llm.openrouter import OpenRouterProvider

        providers.append((OpenRouterProvider, "openrouter"))
    except Exception:  # noqa: S110
        pass
    try:
        from motor.core.llm.lmstudio import LMStudioProvider

        providers.append((LMStudioProvider, "lmstudio"))
    except Exception:  # noqa: S110
        pass
    try:
        from motor.core.llm.vllm import VLLMProvider

        providers.append((VLLMProvider, "vllm"))
    except Exception:  # noqa: S110
        pass
    return providers

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
elif provider_name == "anthropic":
    from motor.core.llm.anthropic import AnthropicProvider

    _default = AnthropicProvider()
    registry.register("anthropic", _default, default=True)
    registry.register("ollama", OllamaProvider())
    log.info("LLM provider set to anthropic (from config)")
elif provider_name == "gemini":
    from motor.core.llm.gemini import GeminiProvider

    _default = GeminiProvider()
    registry.register("gemini", _default, default=True)
    registry.register("ollama", OllamaProvider())
    log.info("LLM provider set to gemini (from config)")
elif provider_name == "openrouter":
    from motor.core.llm.openrouter import OpenRouterProvider

    _default = OpenRouterProvider()
    registry.register("openrouter", _default, default=True)
    registry.register("ollama", OllamaProvider())
    log.info("LLM provider set to openrouter (from config)")
elif provider_name == "lmstudio":
    from motor.core.llm.lmstudio import LMStudioProvider

    _default = LMStudioProvider()
    registry.register("lmstudio", _default, default=True)
    registry.register("ollama", OllamaProvider())
    log.info("LLM provider set to lmstudio (from config)")
elif provider_name == "vllm":
    from motor.core.llm.vllm import VLLMProvider

    _default = VLLMProvider()
    registry.register("vllm", _default, default=True)
    registry.register("ollama", OllamaProvider())
    log.info("LLM provider set to vllm (from config)")
else:
    _default = OllamaProvider()
    registry.register("ollama", _default, default=True)
    for _prov_cls in _get_optional_providers():
        try:
            cls, name = _prov_cls
            registry.register(name, cls())
        except Exception as exc:
            log.debug("%s not available: %s", name, exc)

generate = _default.generate
embed = _default.embed
embed_async = _default.embed_async
health = _default.health

__all__ = ["embed", "embed_async", "generate", "health"]
