"""Tests para motor/core/llm/base.py — Fase 4 (B2)."""

from __future__ import annotations

from typing import Any

import pytest

from motor.core.llm.base import (
    DEFAULT_PROVIDER_CAPABILITIES,
    FALLBACK_EMBEDDING_DIMENSION,
    BaseLLMProvider,
    ProviderValidationResult,
    _check_signature,
    validate_provider,
)


class GoodProvider(BaseLLMProvider):
    _provider_name = "good"

    def generate(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
        return "ok"

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        return [[1.0] * FALLBACK_EMBEDDING_DIMENSION for _ in texts]

    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        return self.embed(texts, model)

    def health(self) -> dict[str, Any]:
        return {"ok": True}


class NoNameProvider(BaseLLMProvider):
    def generate(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
        return "ok"

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        return [[]]

    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        return [[]]

    def health(self) -> dict[str, Any]:
        return {}


class NotProvider:
    def generate(self, prompt: str) -> str:
        return "x"


class TestBaseLLMProvider:
    def test_default_capabilities(self) -> None:
        assert GoodProvider().capabilities == DEFAULT_PROVIDER_CAPABILITIES

    def test_supports_known_bool_true(self) -> None:
        assert GoodProvider().supports("chat") is True

    def test_supports_false_bool(self) -> None:
        assert GoodProvider().supports("streaming") is False

    def test_supports_unknown_capability(self) -> None:
        assert GoodProvider().supports("no_existe") is False

    def test_supports_numeric_positive(self) -> None:
        assert GoodProvider().supports("max_context") is True

    def test_supports_numeric_zero(self) -> None:
        class ZeroCap(GoodProvider):
            @property
            def capabilities(self) -> dict[str, Any]:
                return {"max_context": 0}

        assert ZeroCap().supports("max_context") is False

    def test_abstract_methods(self) -> None:
        with pytest.raises(TypeError):
            BaseLLMProvider()  # type: ignore[abstract]


class TestValidateProvider:
    def test_valid_provider(self) -> None:
        result = validate_provider(GoodProvider)
        assert result.valid is True
        assert result.errors == []
        assert result.provider_name == "good"
        assert "valid=True" in repr(result)

    def test_not_subclass(self) -> None:
        result = validate_provider(NotProvider)
        assert result.valid is False
        assert "No hereda de BaseLLMProvider" in result.errors

    def test_instantiation_failure(self) -> None:
        class Broken(BaseLLMProvider):
            def __init__(self) -> None:
                raise RuntimeError("boom")

            def generate(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
                return ""

            def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return []

            async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return []

            def health(self) -> dict[str, Any]:
                return {}

        result = validate_provider(Broken)
        assert result.valid is False
        assert "No se puede instanciar" in result.errors[0]

    def test_missing_provider_name(self) -> None:
        result = validate_provider(NoNameProvider)
        assert not result.valid
        assert any("Falta _provider_name" in e for e in result.errors)

    def test_missing_method(self) -> None:
        class NoHealth(BaseLLMProvider):
            _provider_name = "nh"

            def generate(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
                return "ok"

            def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return [[]]

            async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return [[]]

        result = validate_provider(NoHealth)
        assert any("health" in e for e in result.errors)

    def test_bad_signature_generate(self) -> None:
        class BadSig(BaseLLMProvider):
            _provider_name = "bad"

            def generate(self, prompt: str) -> str:
                return "ok"

            def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return [[]]

            async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return [[]]

            def health(self) -> dict[str, Any]:
                return {}

        result = validate_provider(BadSig)
        assert any("generate" in e for e in result.errors)
        assert any("model" in e for e in result.errors)

    def test_generate_not_returning_str(self) -> None:
        class BadReturn(BaseLLMProvider):
            _provider_name = "br"

            def generate(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
                return 42  # type: ignore[return-value]

            def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return [[]]

            async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return [[]]

            def health(self) -> dict[str, Any]:
                return {}

        result = validate_provider(BadReturn)
        assert any("generate() no retorna str" in e for e in result.errors)

    def test_missing_chat_capability(self) -> None:
        class NoChat(BaseLLMProvider):
            _provider_name = "nc"

            @property
            def capabilities(self) -> dict[str, Any]:
                caps = dict(DEFAULT_PROVIDER_CAPABILITIES)
                caps.pop("chat")
                return caps

            def generate(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str:
                return "ok"

            def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return [[]]

            async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
                return [[]]

            def health(self) -> dict[str, Any]:
                return {}

        result = validate_provider(NoChat)
        assert any("Falta capacidad 'chat'" in e for e in result.errors)

    def test_invalid_repr(self) -> None:
        result = ProviderValidationResult(False, ["e1", "e2"], "x")
        assert "valid=False" in repr(result)
        assert "e1" in repr(result)


class TestCheckSignature:
    def test_missing_optional_ok(self) -> None:
        def fn(prompt: str, model: str | None = None) -> str:
            return ""

        assert _check_signature(fn, ["prompt", "model"], ["model"]) is None

    def test_missing_param(self) -> None:
        def fn(prompt: str) -> str:
            return ""

        assert _check_signature(fn, ["prompt", "model"], ["model"]) == "falta parámetro 'model'"

    def test_strips_self(self) -> None:
        def fn(self, prompt: str) -> str:
            return ""

        assert _check_signature(fn, ["prompt"], []) is None

    def test_inspect_error(self) -> None:
        result = _check_signature(42, ["x"], [])
        assert result is not None
        assert "error al inspeccionar firma" in result
