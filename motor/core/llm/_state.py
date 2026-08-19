"""LLMState — estado compartido del subsistema LLM.

Fábrica + dataclass frozen. La selección de proveedor se difiere
hasta que build_llm_state() se invoca explícitamente.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger(__name__)


def _get_optional_providers() -> list[tuple[Any, str]]:
    providers: list[tuple[Any, str]] = []
    for mod_path, cls_name, nombre in (
        ("motor.core.llm.openai", "OpenAIProvider", "openai"),
        ("motor.core.llm.anthropic", "AnthropicProvider", "anthropic"),
        ("motor.core.llm.gemini", "GeminiProvider", "gemini"),
        ("motor.core.llm.openrouter", "OpenRouterProvider", "openrouter"),
        ("motor.core.llm.lmstudio", "LMStudioProvider", "lmstudio"),
        ("motor.core.llm.vllm", "VLLMProvider", "vllm"),
        ("motor.core.llm.groq", "GroqProvider", "groq"),
    ):
        try:
            providers.append((getattr(__import__(mod_path, fromlist=[cls_name]), cls_name), nombre))
        except Exception as exc:
            log.debug("%s not available: %s", nombre, exc)
    return providers
    return providers


@dataclass(frozen=True)
class LLMState:
    registry: Any
    default_provider: Any
    generate: Callable
    embed: Callable
    embed_async: Callable
    health: Callable


_PROVIDER_MODULES: dict[str, tuple[str, str]] = {
    "openai": ("motor.core.llm.openai", "OpenAIProvider"),
    "anthropic": ("motor.core.llm.anthropic", "AnthropicProvider"),
    "gemini": ("motor.core.llm.gemini", "GeminiProvider"),
    "openrouter": ("motor.core.llm.openrouter", "OpenRouterProvider"),
    "lmstudio": ("motor.core.llm.lmstudio", "LMStudioProvider"),
    "vllm": ("motor.core.llm.vllm", "VLLMProvider"),
    "groq": ("motor.core.llm.groq", "GroqProvider"),
}


def _seleccionar_provider(provider_name: str, registry: Any, OllamaProvider: type) -> Any:
    """Selecciona y registra el proveedor activo según la configuración."""
    import importlib

    if provider_name in _PROVIDER_MODULES:
        mod_path, cls_name = _PROVIDER_MODULES[provider_name]
        _default = getattr(importlib.import_module(mod_path), cls_name)()
        registry.register(provider_name, _default, default=True)
        registry.register("ollama", OllamaProvider())
        log.info("LLM provider set to %s (from config)", provider_name)
    else:
        _default = OllamaProvider()
        registry.register("ollama", _default, default=True)
        for _prov_cls in _get_optional_providers():
            try:
                cls, name = _prov_cls
                registry.register(name, cls())
            except Exception as exc:
                log.debug("%s not available: %s", name, exc)
    return _default


def build_llm_state(config=None) -> LLMState:
    from motor.core.config import UraConfig
    from motor.core.llm.ollama import OllamaProvider
    from motor.core.llm.registry import registry

    if config is None:
        config = UraConfig.load()

    provider_name = getattr(config, "llm_provider", "ollama")
    _default = _seleccionar_provider(provider_name, registry, OllamaProvider)

    return LLMState(
        registry=registry,
        default_provider=_default,
        generate=_default.generate,
        embed=_default.embed,
        embed_async=_default.embed_async,
        health=_default.health,
    )
