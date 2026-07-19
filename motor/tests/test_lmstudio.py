"""Tests de LMStudioProvider (F22-B6).

Verifica generate, embed, health, capabilities, registry, router, etc.
"""

from __future__ import annotations

from motor.core.llm.base import validate_provider
from motor.core.llm.observability import metrics as global_metrics
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class TestLMStudioProvider:
    def test_lmstudio_importable(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        assert LMStudioProvider is not None

    def test_lmstudio_validate(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        result = validate_provider(LMStudioProvider)
        assert result.valid, f"Errors: {result.errors}"
        assert result.provider_name == "lmstudio"

    def test_lmstudio_generate(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        p = LMStudioProvider()
        r = p.generate("test")
        assert isinstance(r, str)
        assert len(r) > 0

    def test_lmstudio_embed(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        p = LMStudioProvider()
        r = p.embed(["texto"])
        assert isinstance(r, list)
        assert len(r) == 1

    def test_lmstudio_health(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        p = LMStudioProvider()
        h = p.health()
        assert isinstance(h, dict)
        assert "status" in h

    def test_lmstudio_capabilities(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        p = LMStudioProvider()
        caps = p.capabilities
        assert caps["chat"] is True
        assert caps["streaming"] is True
        assert caps["tools"] is False
        assert caps["vision"] is False

    def test_registry_registration(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        reg = ProviderRegistry()
        reg.register("lmstudio", LMStudioProvider(), default=True)
        assert "lmstudio" in reg
        assert reg.get("lmstudio")._provider_name == "lmstudio"

    def test_router_selection(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider
        from motor.core.llm.ollama import OllamaProvider

        reg = ProviderRegistry()
        reg.register("ollama", OllamaProvider(), default=True)
        reg.register("lmstudio", LMStudioProvider())
        router = LLMRouter(registry=reg)
        assert isinstance(router.generate("test", provider="lmstudio"), str)

    def test_retry_integration(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        reg = ProviderRegistry()
        reg.register("lmstudio", LMStudioProvider(), default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=2)
        assert isinstance(router.generate("test"), str)

    def test_breaker_integration(self) -> None:
        from motor.core.llm.lmstudio import LMStudioProvider

        reg = ProviderRegistry()
        reg.register("lmstudio", LMStudioProvider(), default=True)
        router = LLMRouter(registry=reg)
        router.generate("test")

    def test_observability(self) -> None:
        global_metrics.reset()
        from motor.core.llm.lmstudio import LMStudioProvider

        reg = ProviderRegistry()
        reg.register("lmstudio", LMStudioProvider(), default=True)
        router = LLMRouter(registry=reg, fallback_enabled=False)
        router.generate("test")
        assert any("lmstudio" in str(k) for k in global_metrics.get_stats())

    def test_backward_compatibility(self) -> None:
        from motor.core.llm import embed, embed_async, generate, health

        assert callable(generate)
        assert callable(embed)
        assert callable(embed_async)
        assert callable(health)
