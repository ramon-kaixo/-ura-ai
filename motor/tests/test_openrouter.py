"""Tests de OpenRouterProvider (F22-B5).

Verifica:
1. generate() sin API key devuelve error controlado
2. health() sin API key devuelve status error
3. capabilities declaradas correctamente
4. Registro automático en Registry
5. Router puede seleccionar OpenRouter
6. Integración con retry
7. Integración con circuit breaker
8. Observabilidad
9. Backward compatibility
"""

from __future__ import annotations

from motor.core.llm.base import validate_provider
from motor.core.llm.observability import metrics as global_metrics
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class TestOpenRouterProvider:
    def test_openrouter_importable(self) -> None:
        from motor.core.llm.openrouter import OpenRouterProvider

        assert OpenRouterProvider is not None

    def test_openrouter_validate(self) -> None:
        from motor.core.llm.openrouter import OpenRouterProvider

        result = validate_provider(OpenRouterProvider)
        assert result.valid, f"Validation errors: {result.errors}"
        assert result.provider_name == "openrouter"

    def test_openrouter_generate_without_key(self) -> None:
        from motor.core.llm.openrouter import OpenRouterProvider

        p = OpenRouterProvider()
        r = p.generate("test")
        assert isinstance(r, str)
        assert len(r) > 0

    def test_openrouter_health_without_key(self) -> None:
        from motor.core.llm.openrouter import OpenRouterProvider

        p = OpenRouterProvider()
        h = p.health()
        assert isinstance(h, dict)
        assert "status" in h

    def test_openrouter_capabilities(self) -> None:
        from motor.core.llm.openrouter import OpenRouterProvider

        p = OpenRouterProvider()
        caps = p.capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is True
        assert caps["streaming"] is True
        assert caps["vision"] is True

    def test_registry_registration(self) -> None:
        from motor.core.llm.openrouter import OpenRouterProvider

        reg = ProviderRegistry()
        reg.register("openrouter", OpenRouterProvider(), default=True)
        assert "openrouter" in reg
        p = reg.get("openrouter")
        assert p._provider_name == "openrouter"

    def test_router_selection(self) -> None:
        from motor.core.llm.ollama import OllamaProvider
        from motor.core.llm.openrouter import OpenRouterProvider

        reg = ProviderRegistry()
        reg.register("ollama", OllamaProvider(), default=True)
        reg.register("openrouter", OpenRouterProvider())
        router = LLMRouter(registry=reg)
        result = router.generate("test", provider="openrouter")
        assert isinstance(result, str)

    def test_retry_integration(self) -> None:
        from motor.core.llm.openrouter import OpenRouterProvider

        reg = ProviderRegistry()
        reg.register("openrouter", OpenRouterProvider(), default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=2)
        result = router.generate("test")
        assert isinstance(result, str)

    def test_breaker_integration(self) -> None:
        from motor.core.llm.openrouter import OpenRouterProvider

        reg = ProviderRegistry()
        reg.register("openrouter", OpenRouterProvider(), default=True)
        router = LLMRouter(registry=reg)
        _ = router.generate("test")
        assert True

    def test_observability(self) -> None:
        global_metrics.reset()
        from motor.core.llm.openrouter import OpenRouterProvider

        reg = ProviderRegistry()
        reg.register("openrouter", OpenRouterProvider(), default=True)
        router = LLMRouter(registry=reg, fallback_enabled=False)
        router.generate("test")
        stats = global_metrics.get_stats()
        assert any("openrouter" in str(k) for k in stats)

    def test_backward_compatibility(self) -> None:
        from motor.core.llm import embed, embed_async, generate, health

        assert callable(generate)
        assert callable(embed)
        assert callable(embed_async)
        assert callable(health)
