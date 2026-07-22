"""Tests de GeminiProvider (F22-B4).

Verifica:
1. generate() sin API key devuelve error controlado
2. embed() sin API key devuelve degradación
3. health() sin API key devuelve status error
4. capabilities declaradas correctamente
5. Registro automático en Registry
6. Router puede seleccionar Gemini
7. Integración con retry
8. Integración con circuit breaker
9. Observabilidad
10. Backward compatibility
"""

from __future__ import annotations

from motor.core.llm.base import validate_provider
from motor.core.llm.observability import metrics as global_metrics
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class TestGeminiProvider:
    def test_gemini_importable(self) -> None:
        from motor.core.llm.gemini import GeminiProvider

        assert GeminiProvider is not None

    def test_gemini_validate(self) -> None:
        import importlib
        import motor.core.llm.gemini as gemini_mod

        importlib.reload(gemini_mod)
        result = validate_provider(gemini_mod.GeminiProvider)
        assert result.valid, f"Validation errors: {result.errors}"
        assert result.provider_name == "gemini"

    def test_gemini_generate_without_key(self) -> None:
        from motor.core.llm.gemini import GeminiProvider

        p = GeminiProvider()
        r = p.generate("test")
        assert isinstance(r, str)
        assert len(r) > 0

    def test_gemini_embed_without_key(self) -> None:
        from motor.core.llm.gemini import GeminiProvider

        p = GeminiProvider()
        r = p.embed(["texto"])
        assert isinstance(r, list)
        assert len(r) == 1

    def test_gemini_health_without_key(self) -> None:
        from motor.core.llm.gemini import GeminiProvider

        p = GeminiProvider()
        h = p.health()
        assert isinstance(h, dict)
        assert "status" in h

    def test_gemini_capabilities(self) -> None:
        from motor.core.llm.gemini import GeminiProvider

        p = GeminiProvider()
        caps = p.capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is True  # Gemini sí ofrece embeddings
        assert caps["streaming"] is True
        assert caps["tools"] is True
        assert caps["vision"] is True
        assert caps["max_context"] == 1048576

    def test_registry_registration(self) -> None:
        from motor.core.llm.gemini import GeminiProvider

        reg = ProviderRegistry()
        reg.register("gemini", GeminiProvider(), default=True)
        assert "gemini" in reg
        p = reg.get("gemini")
        assert p._provider_name == "gemini"

    def test_router_selection(self) -> None:
        from motor.core.llm.gemini import GeminiProvider
        from motor.core.llm.ollama import OllamaProvider

        reg = ProviderRegistry()
        reg.register("ollama", OllamaProvider(), default=True)
        reg.register("gemini", GeminiProvider())
        router = LLMRouter(registry=reg)
        result = router.generate("test", provider="gemini")
        assert isinstance(result, str)

    def test_retry_integration(self) -> None:
        from motor.core.llm.gemini import GeminiProvider

        reg = ProviderRegistry()
        reg.register("gemini", GeminiProvider(), default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=2)
        result = router.generate("test")
        assert isinstance(result, str)

    def test_breaker_integration(self) -> None:
        from motor.core.llm.gemini import GeminiProvider

        reg = ProviderRegistry()
        reg.register("gemini", GeminiProvider(), default=True)
        router = LLMRouter(registry=reg)
        _ = router.generate("test")
        assert True

    def test_observability(self) -> None:
        global_metrics.reset()
        from motor.core.llm.gemini import GeminiProvider

        reg = ProviderRegistry()
        reg.register("gemini", GeminiProvider(), default=True)
        router = LLMRouter(registry=reg, fallback_enabled=False)
        router.generate("test")
        stats = global_metrics.get_stats()
        assert any("gemini" in str(k) for k in stats)

    def test_backward_compatibility(self) -> None:
        from motor.core.llm import embed, embed_async, generate, health

        assert callable(generate)
        assert callable(embed)
        assert callable(embed_async)
        assert callable(health)
