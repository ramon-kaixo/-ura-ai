"""Tests del benchmark multi-proveedor (F22-B8)."""





from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow  # G4: requieren scripts/servicios de benchmark pesados

import json
from pathlib import Path

from motor.core.llm.base import BaseLLMProvider
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter





class _MockOK(BaseLLMProvider):
    def __init__(self):
        self._provider_name = "mock_ok"

    def generate(self, prompt, model=None, options=None):
        return "ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class _MockFail(BaseLLMProvider):
    def __init__(self):
        self._provider_name = "mock_fail"

    def generate(self, prompt, model=None, options=None):
        msg = "fail"
        raise ValueError(msg)

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class TestBenchmarkAllProviders:
    def test_missing_provider(self) -> None:
        """Proveedor no registrado debe lanzar error."""
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)

        with pytest.raises(RuntimeError):
            router.generate("test", provider="nonexistent")

    def test_partial_failures(self) -> None:
        """Un proveedor que falla no debe afectar a otros."""
        reg = ProviderRegistry()
        reg.register("fails", _MockFail(), default=True)
        reg.register("works", _MockOK())
        router = LLMRouter(registry=reg, fallback_enabled=False)
        r_works = router.generate("test", provider="works")
        assert r_works == "ok"
        r_fails = router.generate("test", provider="fails")
        assert "Error" in r_fails

    def test_backward_compatibility(self) -> None:
        from motor.core.llm import embed, embed_async, generate, health

        assert callable(generate)
        assert callable(embed)
        assert callable(embed_async)
        assert callable(health)
