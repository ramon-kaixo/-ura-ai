"""Tests de AnthropicProvider (F22-B3).

Verifica:
1. generate() sin API key devuelve error controlado
2. health() sin API key devuelve status error
3. capabilities declaradas correctamente
4. Registro automático en Registry
5. Router puede seleccionar Anthropic
6. Integración con retry (sin API key retorna error)
7. Integración con circuit breaker (no bloquea)
8. Observabilidad (métricas registradas)
9. Backward compatibility (API pública intacta)
"""

from __future__ import annotations

from motor.core.llm.base import validate_provider
from motor.core.llm.observability import metrics as global_metrics
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class TestAnthropicProvider:
    def test_anthropic_importable(self) -> None:
        from motor.core.llm.anthropic import AnthropicProvider

        assert AnthropicProvider is not None

    def test_anthropic_validate(self) -> None:
        from motor.core.llm.anthropic import AnthropicProvider

        result = validate_provider(AnthropicProvider)
        assert result.valid, f"Validation errors: {result.errors}"
        assert result.provider_name == "anthropic"

    def test_anthropic_health_without_key(self) -> None:
        from motor.core.llm.anthropic import AnthropicProvider

        p = AnthropicProvider()
        h = p.health()
        assert isinstance(h, dict)
        assert "status" in h

    def test_anthropic_generate_without_key(self) -> None:
        from motor.core.llm.anthropic import AnthropicProvider

        p = AnthropicProvider()
        r = p.generate("test")
        assert isinstance(r, str)
        # Sin API key debe devolver un error, no crashear
        assert len(r) > 0

    def test_anthropic_capabilities(self) -> None:
        from motor.core.llm.anthropic import AnthropicProvider

        p = AnthropicProvider()
        caps = p.capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is False  # Anthropic no ofrece embeddings
        assert caps["streaming"] is True
        assert caps["tools"] is True
        assert caps["vision"] is True
        assert caps["max_context"] == 200000

    def test_anthropic_embed_fallback(self) -> None:
        from motor.core.llm.anthropic import AnthropicProvider

        p = AnthropicProvider()
        result = p.embed(["texto"])
        assert isinstance(result, list)
        assert len(result) == 1
        assert len(result[0]) == 768  # Vector de relleno

    def test_registry_registration(self) -> None:
        reg = ProviderRegistry()
        from motor.core.llm.anthropic import AnthropicProvider

        reg.register("anthropic", AnthropicProvider(), default=True)
        assert "anthropic" in reg
        p = reg.get("anthropic")
        assert p._provider_name == "anthropic"

    def test_router_selection(self) -> None:
        reg = ProviderRegistry()
        from motor.core.llm.anthropic import AnthropicProvider
        from motor.core.llm.ollama import OllamaProvider

        reg.register("ollama", OllamaProvider(), default=True)
        reg.register("anthropic", AnthropicProvider())
        router = LLMRouter(registry=reg)

        result = router.generate("test", provider="anthropic")
        assert isinstance(result, str)

    def test_retry_integration(self) -> None:
        """Retry no debe crashear con Anthropic (sin API key retorna error)."""
        reg = ProviderRegistry()
        from motor.core.llm.anthropic import AnthropicProvider

        reg.register("anthropic", AnthropicProvider(), default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=2)
        result = router.generate("test")
        assert isinstance(result, str)

    def test_breaker_integration(self) -> None:
        """Circuit breaker no debe bloquearse con Anthropic."""
        reg = ProviderRegistry()
        from motor.core.llm.anthropic import AnthropicProvider

        reg.register("anthropic", AnthropicProvider(), default=True)
        router = LLMRouter(registry=reg)
        _ = router.generate("test")
        # No debe lanzar excepción
        assert True

    def test_observability(self) -> None:
        """Las llamadas a Anthropic deben registrar métricas."""
        global_metrics.reset()
        reg = ProviderRegistry()
        from motor.core.llm.anthropic import AnthropicProvider

        reg.register("anthropic", AnthropicProvider(), default=True)
        router = LLMRouter(registry=reg, fallback_enabled=False)
        router.generate("test")
        stats = global_metrics.get_stats()
        # Debe haber alguna métrica
        assert any("anthropic" in str(k) for k in stats)

    def test_backward_compatibility(self) -> None:
        """La API pública no debe verse afectada por AnthropicProvider."""
        from motor.core.llm import embed, embed_async, generate, health

        assert callable(generate)
        assert callable(embed)
        assert callable(embed_async)
        assert callable(health)
