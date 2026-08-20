"""Tests de cobertura para motor/core/llm/router/providers.py (gate 90%)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from motor.core.llm.router.providers import DEFAULT_ROUTES, resolve, resolve_name


class RegistryStub:
    def __init__(self, providers: list[str], default: str | None) -> None:
        self._providers = providers
        self._default = default
        self._getter = MagicMock()

    def __contains__(self, name: str) -> bool:
        return name in self._providers

    def list(self) -> list[str]:
        return list(self._providers)

    def get(self, name: str):
        return self._getter(name)

    @property
    def default_name(self) -> str | None:
        return self._default


class TestResolve:
    def test_provider_explicito(self) -> None:
        reg = RegistryStub(["ollama", "openai"], "ollama")
        resolve("generate", "openai", reg, DEFAULT_ROUTES)
        reg._getter.assert_called_once_with("openai")

    def test_provider_no_registrado_raise(self) -> None:
        reg = RegistryStub(["ollama"], "ollama")
        with pytest.raises(RuntimeError, match="not in registry"):
            resolve("generate", "gemini", reg, DEFAULT_ROUTES)

    def test_por_ruta(self) -> None:
        reg = RegistryStub(["ollama"], "ollama")
        resolve("generate", None, reg, {"generate": "ollama"})
        reg._getter.assert_called_once_with("ollama")

    def test_ruta_fallback_default(self) -> None:
        reg = RegistryStub(["openai"], "openai")
        resolve("vision", None, reg, {"generate": "ollama"})
        reg._getter.assert_called_once_with("openai")

    def test_sin_ruta_sin_default_raise(self) -> None:
        reg = RegistryStub([], None)
        with pytest.raises(RuntimeError, match="No provider available"):
            resolve("vision", None, reg, {})

    def test_ruta_no_registrada_sin_fallback_raise(self) -> None:
        reg = RegistryStub([], None)
        with pytest.raises(RuntimeError, match="unregistered provider"):
            resolve("generate", None, reg, {"generate": "ollama"})


class TestResolveName:
    def test_provider_explicito(self) -> None:
        reg = RegistryStub(["ollama"], "ollama")
        assert resolve_name("generate", "openai", reg, DEFAULT_ROUTES) == "openai"

    def test_por_ruta(self) -> None:
        reg = RegistryStub(["ollama"], "ollama")
        assert resolve_name("generate", None, reg, {"generate": "ollama"}) == "ollama"

    def test_ruta_no_registrada_fallback(self) -> None:
        reg = RegistryStub(["openai"], "openai")
        assert resolve_name("generate", None, reg, {"generate": "ollama"}) == "openai"

    def test_sin_nada_unknown(self) -> None:
        reg = RegistryStub([], None)
        assert resolve_name("vision", None, reg, {}) == "unknown"


class TestDefaultRoutes:
    def test_rutas_por_defecto(self) -> None:
        assert DEFAULT_ROUTES == {"generate": "ollama", "embed": "ollama", "health": "ollama"}
