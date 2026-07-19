"""Tests de negociación de capacidades de proveedores (F22-B2).

Verifica:
1. Capacidades declarativas de cada proveedor
2. Router selecciona por capacidad
3. Capacidad no soportada → error
4. Múltiples proveedores capaces
5. Backward compatibility (capabilities por defecto)
6. Registry + capabilities
7. Health no modifica capabilities
"""

from __future__ import annotations

from motor.core.llm.base import DEFAULT_PROVIDER_CAPABILITIES, BaseLLMProvider
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter

# ── Proveedores mock con capacidades declarativas ─────────


class _BasicProvider(BaseLLMProvider):
    """Proveedor básico con capacidades por defecto (solo chat + embeddings)."""

    def __init__(self) -> None:
        self._provider_name = "basic"

    def generate(self, prompt, model=None, options=None):
        return "ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class _VisionProvider(BaseLLMProvider):
    """Proveedor con capacidades de visión."""

    def __init__(self) -> None:
        self._provider_name = "vision_pro"

    @property
    def capabilities(self) -> dict:
        caps = dict(DEFAULT_PROVIDER_CAPABILITIES)
        caps["vision"] = True
        caps["multimodal"] = True
        caps["max_context"] = 128000
        return caps

    def generate(self, prompt, model=None, options=None):
        return "vision_ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class _StreamingProvider(BaseLLMProvider):
    """Proveedor con streaming."""

    def __init__(self) -> None:
        self._provider_name = "stream_pro"

    @property
    def capabilities(self) -> dict:
        caps = dict(DEFAULT_PROVIDER_CAPABILITIES)
        caps["streaming"] = True
        caps["max_output"] = 8192
        return caps

    def generate(self, prompt, model=None, options=None):
        return "stream_ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class TestProviderCapabilities:
    def test_default_capabilities(self) -> None:
        """Proveedor sin sobrescribir capabilities debe tener valores por defecto."""
        p = _BasicProvider()
        caps = p.capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is True
        assert caps["streaming"] is False
        assert caps["tools"] is False
        assert caps["max_context"] == 4096
        assert caps["max_output"] == 1024

    def test_vision_capabilities(self) -> None:
        p = _VisionProvider()
        assert p.supports("vision") is True
        assert p.supports("multimodal") is True
        assert p.supports("chat") is True
        assert p.supports("streaming") is False

    def test_streaming_capabilities(self) -> None:
        p = _StreamingProvider()
        assert p.supports("streaming") is True
        assert p.supports("vision") is False
        assert p.capabilities["max_output"] == 8192

    def test_supports_unknown_capability(self) -> None:
        p = _BasicProvider()
        assert p.supports("nonexistent") is False

    def test_ollama_capabilities(self) -> None:
        from motor.core.llm.ollama import OllamaProvider

        p = OllamaProvider()
        assert p.supports("chat") is True
        assert p.supports("embeddings") is True
        assert p.supports("vision") is True
        assert p.capabilities["max_context"] == 32768

    def test_openai_capabilities(self) -> None:
        from motor.core.llm.openai import OpenAIProvider

        p = OpenAIProvider()
        assert p.supports("chat") is True
        assert p.supports("streaming") is True
        assert p.supports("vision") is True
        assert p.supports("tools") is True
        assert p.capabilities["max_context"] == 128000


class TestRouterCapabilitySelection:
    def test_select_by_capability(self) -> None:
        reg = ProviderRegistry()
        reg.register("basic", _BasicProvider(), default=True)
        reg.register("vision", _VisionProvider())
        router = LLMRouter(registry=reg)

        name = router.select_provider_by_capability("vision")
        assert name == "vision"

    def test_select_by_capability_preferred(self) -> None:
        reg = ProviderRegistry()
        reg.register("basic", _BasicProvider(), default=True)
        reg.register("vision", _VisionProvider())
        router = LLMRouter(registry=reg)

        name = router.select_provider_by_capability("vision", preferred="basic")
        # basic no soporta vision, debe elegir vision_pro
        assert name == "vision"

    def test_capability_not_supported(self) -> None:
        reg = ProviderRegistry()
        reg.register("basic", _BasicProvider(), default=True)
        router = LLMRouter(registry=reg)

        import pytest

        with pytest.raises(RuntimeError, match="vision"):
            router.select_provider_by_capability("vision")

    def test_multiple_capable_providers(self) -> None:
        reg = ProviderRegistry()
        reg.register("v1", _VisionProvider())
        reg.register("v2", _VisionProvider())
        router = LLMRouter(registry=reg)

        capable = router.find_providers_by_capability("vision")
        assert len(capable) == 2
        assert "v1" in capable
        assert "v2" in capable

    def test_capability_validation(self) -> None:
        """validate_provider debe verificar capabilities."""
        from motor.core.llm.base import validate_provider

        result = validate_provider(_VisionProvider)
        assert result.valid

    def test_backwards_compatibility(self) -> None:
        """Proveedores existentes siguen funcionando sin capabilities explícitas."""
        p = _BasicProvider()
        # El método generate debe funcionar igual
        assert p.generate("test") == "ok"
        assert p.embed(["test"]) == [[0.0]]
        # capabilities deben tener valores por defecto
        assert p.capabilities["chat"] is True

    def test_registry_capabilities(self) -> None:
        """Registry + capabilities: listar proveedores por capacidad."""
        reg = ProviderRegistry()
        reg.register("basic", _BasicProvider(), default=True)
        reg.register("vision", _VisionProvider())

        vision_providers = [name for name in reg.list() if reg.get(name).supports("vision")]
        assert "vision" in vision_providers
        assert "basic" not in vision_providers

    def test_generate_with_capability(self) -> None:
        reg = ProviderRegistry()
        reg.register("basic", _BasicProvider(), default=True)
        reg.register("stream", _StreamingProvider())
        router = LLMRouter(registry=reg)

        result = router.generate_with_capability("test", capability="streaming")
        assert result == "stream_ok"

    def test_health_preserves_capabilities(self) -> None:
        """health() no debe alterar las capabilities declaradas."""
        p = _VisionProvider()
        caps_before = dict(p.capabilities)
        p.health()
        caps_after = p.capabilities
        assert caps_before == caps_after
