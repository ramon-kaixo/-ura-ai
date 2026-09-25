#!/usr/bin/env python3
from typing import Any
"""Cobertura 100x100 de motor/core/llm/base.py."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.llm.base import BaseLLMProvider, DEFAULT_PROVIDER_CAPABILITIES, FALLBACK_EMBEDDING_DIMENSION


def make_concrete_provider():
    """Factory para crear proveedor concreto con métodos abstractos."""
    class ConcreteProvider:
        def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
            return "test"
        def embed(self, texts: list[str], model: str | None = None, options: dict | None = None):
            return [[0.0] * 768]
        async def embed_async(self, texts: list[str], model: str | None = None, options: dict | None = None):
            return [[0.0] * 768]
        def health(self) -> dict:
            return {"status": "ok", "modelos_disponibles": ["test"]}
    return type('ConcreteProvider', (BaseLLMProvider,), {
        'generate': lambda self, prompt, model=None, options=None: "test",
        'embed': lambda self, texts, model=None, options=None: [[0.0] * 768],
        'embed_async': lambda self, texts, model=None, options=None: [[0.0] * 768],
        'health': lambda self: {"status": "ok"}
    })


class TestDefaultCapabilities:
    @pytest.mark.unit
    def test_fallback_embedding_dimension(self):
        from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION
        assert FALLBACK_EMBEDDING_DIMENSION == 768

    @pytest.mark.unit
    def test_default_capabilities_keys(self):
        from motor.core.llm.base import DEFAULT_PROVIDER_CAPABILITIES
        expected_keys = {"chat", "embeddings", "streaming", "tools", "json_mode", "multimodal", "vision", "max_context", "max_output"}
        assert set(DEFAULT_PROVIDER_CAPABILITIES.keys()) == expected_keys

    @pytest.mark.unit
    def test_default_capabilities_types(self):
        from motor.core.llm.base import DEFAULT_PROVIDER_CAPABILITIES
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["chat"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["embeddings"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["streaming"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["tools"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["json_mode"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["multimodal"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["vision"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["max_context"], int)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["max_output"], int)


class TestBaseLLMProvider:
    @pytest.mark.unit
    def test_cannot_instantiate_abstract(self):
        from motor.core.llm.base import BaseLLMProvider
        with pytest.raises(TypeError):
            BaseLLMProvider()

    @pytest.mark.unit
    def test_capabilities_returns_copy(self):
        from motor.core.llm.base import BaseLLMProvider, DEFAULT_PROVIDER_CAPABILITIES
        
        ProviderClass = type('ConcreteProvider', (BaseLLMProvider,), {
            'generate': lambda self, prompt, model=None, options=None: "test",
            'embed': lambda self, texts, model=None, options=None: [[0.0] * 768],
            'embed_async': lambda self, texts, model=None, options=None: [[0.0] * 768],
            'health': lambda self: {"status": "ok"}
        })
        
        provider = ProviderClass()
        caps = provider.capabilities
        assert caps == DEFAULT_PROVIDER_CAPABILITIES
        caps["test"] = "modified"
        assert "test" not in DEFAULT_PROVIDER_CAPABILITIES


class TestCapabilitiesSupports:
    @pytest.mark.unit
    def make_provider(self):
        return type('ConcreteProvider', (BaseLLMProvider,), {
            'generate': lambda self, prompt, model=None, options=None: "test",
            'embed': lambda self, texts, model=None, options=None: [[0.0] * 768],
            'embed_async': lambda self, texts, model=None, options=None: [[0.0] * 768],
            'health': lambda self: {"status": "ok"}
        })()

    @pytest.mark.unit
    def test_supports_bool_true(self):
        provider = self.make_provider()
        assert provider.supports("chat") is True
        assert provider.supports("embeddings") is True

    @pytest.mark.unit
    def test_supports_bool_false(self):
        provider = self.make_provider()
        assert provider.supports("streaming") is False
        assert provider.supports("tools") is False
        assert provider.supports("json_mode") is False
        assert provider.supports("multimodal") is False
        assert provider.supports("vision") is False

    @pytest.mark.unit
    def test_supports_int_positive(self):
        provider = self.make_provider()
        assert provider.supports("max_context") is True
        assert provider.supports("max_output") is True

    @pytest.mark.unit
    def test_supports_unknown(self):
        provider = self.make_provider()
        assert provider.supports("unknown_capability") is False


class TestGenerateStream:
    @pytest.mark.unit
    def test_generate_stream_degraded(self):
        """Por defecto emite resultado de generate() como un fragmento."""
        from motor.core.llm.base import BaseLLMProvider
        
        class TestProvider(BaseLLMProvider):
            def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
                return "resultado completo"
            def embed(self, texts, model=None, options=None): return [[0.0]*768]
            async def embed_async(self, texts, model=None, options=None): return [[0.0]*768]
            def health(self): return {"status": "ok"}
        
        provider = type('TestProvider', (BaseLLMProvider,), {
            'generate': lambda self, prompt, model=None, options=None: "resultado completo",
            'embed': lambda self, texts, model=None, options=None: [[0.0]*768],
            'embed_async': lambda self, texts, model=None, options=None: [[0.0]*768],
            'health': lambda self: {"status": "ok"}
        })()
        
        chunks = list(provider.generate_stream("test prompt"))
        assert chunks == ["resultado completo"]


class TestChatGenerate:
    @pytest.mark.unit
    def test_chat_generate_default(self):
        from motor.core.llm.base import BaseLLMProvider
        
        class ConcreteProvider:
            def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
                return "respuesta chat"
            def embed(self, texts, model=None, options=None): return [[0.0]*768]
            async def embed_async(self, texts, model=None, options=None): return [[0.0]*768]
            def health(self): return {"status": "ok"}
            
            def chat_generate(self, mensajes: list[dict[str, str]], model: str | None = None, 
                              tools: list[dict[str, object]] | None = None, 
                              options: dict | None = None) -> dict[str, Any]:
                return {"role": "assistant", "content": self.generate("test")}
        
        provider = type('Concrete', (BaseLLMProvider,), {
            'generate': lambda self, prompt, model=None, options=None: "respuesta chat",
            'embed': lambda self, texts, model=None, options=None: [[0.0]*768],
            'embed_async': lambda self, texts, model=None, options=None: [[0.0]*768],
            'health': lambda self: {"status": "ok"},
            'chat_generate': lambda self, mensajes, model=None, tools=None, options=None: {"role": "assistant", "content": "respuesta chat"}
        })()
        
        resultado = provider.chat_generate([{"role": "user", "content": "hola"}])
        assert resultado["role"] == "assistant"
        assert resultado["content"] == "respuesta chat"


class TestDefaultCapabilities:
    @pytest.mark.unit
    def test_fallback_embedding_dimension(self):
        from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION
        assert FALLBACK_EMBEDDING_DIMENSION == 768

    @pytest.mark.unit
    def test_default_capabilities_keys(self):
        from motor.core.llm.base import DEFAULT_PROVIDER_CAPABILITIES
        expected_keys = {"chat", "embeddings", "streaming", "tools", "json_mode", "multimodal", "vision", "max_context", "max_output"}
        assert set(DEFAULT_PROVIDER_CAPABILITIES.keys()) == expected_keys

    @pytest.mark.unit
    def test_default_capabilities_types(self):
        from motor.core.llm.base import DEFAULT_PROVIDER_CAPABILITIES
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["chat"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["embeddings"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["streaming"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["tools"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["json_mode"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["multimodal"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["vision"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["max_context"], int)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["max_output"], int)


class TestCapabilitiesSupports:
    def make_provider(self):
        provider = type('ConcreteProvider', (BaseLLMProvider,), {
            'generate': lambda self, prompt, model=None, options=None: "test",
            'embed': lambda self, texts, model=None, options=None: [[0.0] * 768],
            'embed_async': lambda self, texts, model=None, options=None: [[0.0]*768],
            'health': lambda self: {"status": "ok"}
        })()
        return provider

    @pytest.mark.unit
    def test_supports_bool_true(self):
        provider = self.make_provider()
        assert provider.supports("chat") is True
        assert provider.supports("embeddings") is True

    @pytest.mark.unit
    def test_supports_bool_false(self):
        provider = self.make_provider()
        assert provider.supports("streaming") is False
        assert provider.supports("tools") is False
        assert provider.supports("json_mode") is False
        assert provider.supports("multimodal") is False
        assert provider.supports("vision") is False

    @pytest.mark.unit
    def test_supports_int_positive(self):
        provider = self.make_provider()
        assert provider.supports("max_context") is True
        assert provider.supports("max_output") is True

    @pytest.mark.unit
    def test_supports_unknown(self):
        provider = self.make_provider()
        assert provider.supports("unknown_capability") is False


class TestGenerateStream:
    @pytest.mark.unit
    def test_generate_stream_degraded(self):
        from motor.core.llm.base import BaseLLMProvider
        
        class TestProvider(BaseLLMProvider):
            def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
                return "resultado completo"
            def embed(self, texts, model=None, options=None): return [[0.0]*768]
            async def embed_async(self, texts, model=None, options=None): return [[0.0]*768]
            def health(self): return {"status": "ok"}
        
        provider = type('TestProvider', (BaseLLMProvider,), {
            'generate': lambda self, prompt, model=None, options=None: "resultado completo",
            'embed': lambda self, texts, model=None, options=None: [[0.0]*768],
            'embed_async': lambda self, texts, model=None, options=None: [[0.0]*768],
            'health': lambda self: {"status": "ok"}
        })()
        
        chunks = list(provider.generate_stream("test prompt"))
        assert chunks == ["resultado completo"]


class TestChatGenerate:
    @pytest.mark.unit
    def test_chat_generate_default(self):
        from motor.core.llm.base import BaseLLMProvider
        
        class ConcreteProvider:
            def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
                return "respuesta chat"
            def embed(self, texts, model=None, options=None): return [[0.0]*768]
            async def embed_async(self, texts, model=None, options=None): return [[0.0]*768]
            def health(self): return {"status": "ok"}
            
            def chat_generate(self, mensajes: list[dict[str, str]], model: str | None = None, 
                              tools: list[dict[str, object]] | None = None, 
                              options: dict | None = None) -> dict[str, Any]:
                return {"role": "assistant", "content": self.generate("test")}
        
        provider = type('Concrete', (BaseLLMProvider,), {
            'generate': lambda self, prompt, model=None, options=None: "respuesta chat",
            'embed': lambda self, texts, model=None, options=None: [[0.0]*768],
            'embed_async': lambda self, texts, model=None, options=None: [[0.0]*768],
            'health': lambda self: {"status": "ok"},
            'chat_generate': lambda self, mensajes, model=None, tools=None, options=None: {"role": "assistant", "content": "respuesta chat"}
        })()
        
        resultado = provider.chat_generate([{"role": "user", "content": "hola"}])
        assert resultado["role"] == "assistant"
        assert resultado["content"] == "respuesta chat"


class TestDefaultCapabilities:
    @pytest.mark.unit
    def test_fallback_embedding_dimension(self):
        from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION
        assert FALLBACK_EMBEDDING_DIMENSION == 768

    @pytest.mark.unit
    def test_default_capabilities_keys(self):
        from motor.core.llm.base import DEFAULT_PROVIDER_CAPABILITIES
        expected_keys = {"chat", "embeddings", "streaming", "tools", "json_mode", "multimodal", "vision", "max_context", "max_output"}
        assert set(DEFAULT_PROVIDER_CAPABILITIES.keys()) == expected_keys

    @pytest.mark.unit
    def test_default_capabilities_types(self):
        from motor.core.llm.base import DEFAULT_PROVIDER_CAPABILITIES
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["chat"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["embeddings"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["streaming"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["tools"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["json_mode"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["multimodal"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["vision"], bool)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["max_context"], int)
        assert isinstance(DEFAULT_PROVIDER_CAPABILITIES["max_output"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
