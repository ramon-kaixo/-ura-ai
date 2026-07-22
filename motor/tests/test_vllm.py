"""Tests de VLLMProvider (F22-B7)."""

from __future__ import annotations

from motor.core.llm.base import validate_provider
from motor.core.llm.observability import metrics as g
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class TestVLLMProvider:
    def test_vllm_importable(self) -> None:
        from motor.core.llm.vllm import VLLMProvider

        assert VLLMProvider is not None

    def test_vllm_validate(self) -> None:
        """Valida que la clase cumple el contrato BaseLLMProvider sin conexión real."""
        import importlib

        from unittest.mock import patch

        secrets = {
            "VLLM_BASE_URL": "http://localhost:8000/v1",
            "VLLM_MODEL": "local-model",
            "VLLM_TIMEOUT": "120",
            "VLLM_TEMPERATURE": "0.3",
            "VLLM_MAX_TOKENS": "1024",
        }

        def mock_get_secret(name: str, default: str = "") -> str:
            return secrets.get(name, default)

        with patch("motor.core.llm.vllm.get_secret", side_effect=mock_get_secret):
            import motor.core.llm.vllm as vllm_mod

            importlib.reload(vllm_mod)
            r = validate_provider(vllm_mod.VLLMProvider)
            assert r.valid, f"VLLMProvider no válido: {r.errors}"
            assert r.provider_name == "vllm"

    def test_vllm_generate(self) -> None:
        from motor.core.llm.vllm import VLLMProvider

        r = VLLMProvider().generate("test")
        assert isinstance(r, str)
        assert len(r) > 0

    def test_vllm_embed(self) -> None:
        from motor.core.llm.vllm import VLLMProvider

        r = VLLMProvider().embed(["texto"])
        assert isinstance(r, list)
        assert len(r) == 1

    def test_vllm_health(self) -> None:
        from motor.core.llm.vllm import VLLMProvider

        h = VLLMProvider().health()
        assert isinstance(h, dict)
        assert "status" in h

    def test_vllm_capabilities(self) -> None:
        from motor.core.llm.vllm import VLLMProvider

        c = VLLMProvider().capabilities
        assert c["chat"]
        assert c["embeddings"]
        assert c["streaming"]
        assert c["vision"] is False
        assert c["max_context"] == 32768

    def test_registry(self) -> None:
        from motor.core.llm.vllm import VLLMProvider

        reg = ProviderRegistry()
        reg.register("vllm", VLLMProvider(), default=True)
        assert reg.get("vllm")._provider_name == "vllm"

    def test_router(self) -> None:
        from motor.core.llm.ollama import OllamaProvider
        from motor.core.llm.vllm import VLLMProvider

        reg = ProviderRegistry()
        reg.register("ollama", OllamaProvider(), default=True)
        reg.register("vllm", VLLMProvider())
        assert isinstance(LLMRouter(registry=reg).generate("test", provider="vllm"), str)

    def test_retry(self) -> None:
        from motor.core.llm.vllm import VLLMProvider

        reg = ProviderRegistry()
        reg.register("vllm", VLLMProvider(), default=True)
        assert isinstance(LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=2).generate("test"), str)

    def test_breaker(self) -> None:
        from motor.core.llm.vllm import VLLMProvider

        reg = ProviderRegistry()
        reg.register("vllm", VLLMProvider(), default=True)
        LLMRouter(registry=reg).generate("test")

    def test_observability(self) -> None:
        g.reset()
        from motor.core.llm.vllm import VLLMProvider

        reg = ProviderRegistry()
        reg.register("vllm", VLLMProvider(), default=True)
        LLMRouter(registry=reg, fallback_enabled=False).generate("test")
        assert any("vllm" in str(k) for k in g.get_stats())

    def test_backward(self) -> None:
        from motor.core.llm import embed, embed_async, generate, health

        assert callable(generate)
        assert callable(embed)
        assert callable(embed_async)
        assert callable(health)
