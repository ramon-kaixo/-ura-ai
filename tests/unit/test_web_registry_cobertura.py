"""Cobertura 100x100 de motor/core/web/registry.py (TASK-20260815-003).

Cubre el registro de proveedores de los seis tipos (searchers, crawlers,
extractors, rankers, summarizers, validators): registro, acceso, listado
y errores KeyError para nombres inexistentes.

Sin dependencias externas: solo motor.core.web + stdlib.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from motor.core.web.registry import Registry


def _provider(name: str = "p") -> SimpleNamespace:
    return SimpleNamespace(name=name)


class TestRegistrySearchers:
    """Registro de buscadores."""

    def test_register_get_list(self) -> None:
        r = Registry()
        p = _provider("ddg")
        r.register_searcher("ddg", p)
        assert r.get_searcher("ddg") is p
        assert r.list_searchers() == ["ddg"]

    def test_get_inexistente_raise(self) -> None:
        with pytest.raises(KeyError):
            Registry().get_searcher("nope")

    def test_list_vacio(self) -> None:
        assert Registry().list_searchers() == []


class TestRegistryCrawlers:
    """Registro de crawlers."""

    def test_register_get_list(self) -> None:
        r = Registry()
        p = _provider("httpx")
        r.register_crawler("httpx", p)
        assert r.get_crawler("httpx") is p
        assert r.list_crawlers() == ["httpx"]

    def test_get_inexistente_raise(self) -> None:
        with pytest.raises(KeyError):
            Registry().get_crawler("nope")

    def test_list_vacio(self) -> None:
        assert Registry().list_crawlers() == []


class TestRegistryExtractors:
    """Registro de extractores."""

    def test_register_get_list(self) -> None:
        r = Registry()
        p = _provider("html")
        r.register_extractor("html", p)
        assert r.get_extractor("html") is p
        assert r.list_extractors() == ["html"]

    def test_get_inexistente_raise(self) -> None:
        with pytest.raises(KeyError):
            Registry().get_extractor("nope")

    def test_list_vacio(self) -> None:
        assert Registry().list_extractors() == []


class TestRegistryRankers:
    """Registro de rankers."""

    def test_register_get_list(self) -> None:
        r = Registry()
        p = _provider("default")
        r.register_ranker("default", p)
        assert r.get_ranker("default") is p
        assert r.list_rankers() == ["default"]

    def test_get_inexistente_raise(self) -> None:
        with pytest.raises(KeyError):
            Registry().get_ranker("nope")

    def test_list_vacio(self) -> None:
        assert Registry().list_rankers() == []


class TestRegistrySummarizers:
    """Registro de summarizers."""

    def test_register_get_list(self) -> None:
        r = Registry()
        p = _provider("llm")
        r.register_summarizer("llm", p)
        assert r.get_summarizer("llm") is p
        assert r.list_summarizers() == ["llm"]

    def test_get_inexistente_raise(self) -> None:
        with pytest.raises(KeyError):
            Registry().get_summarizer("nope")

    def test_list_vacio(self) -> None:
        assert Registry().list_summarizers() == []


class TestRegistryValidators:
    """Registro de validadores."""

    def test_register_get_list(self) -> None:
        r = Registry()
        p = _provider("v")
        r.register_validator("v", p)
        assert r.get_validator("v") is p
        assert r.list_validators() == ["v"]

    def test_get_inexistente_raise(self) -> None:
        with pytest.raises(KeyError):
            Registry().get_validator("nope")

    def test_list_vacio(self) -> None:
        assert Registry().list_validators() == []


class TestRegistrySobreescritura:
    """Sobreescritura de proveedores con el mismo nombre."""

    def test_register_mismo_nombre_reemplaza(self) -> None:
        r = Registry()
        p1 = _provider("a")
        p2 = _provider("b")
        r.register_searcher("x", p1)
        r.register_searcher("x", p2)
        assert r.get_searcher("x") is p2
        assert r.list_searchers() == ["x"]

    def test_independencia_entre_tipos(self) -> None:
        """El mismo nombre puede existir en tipos distintos sin colisión."""
        r = Registry()
        r.register_searcher("x", _provider("s"))
        r.register_crawler("x", _provider("c"))
        assert r.list_searchers() == ["x"]
        assert r.list_crawlers() == ["x"]
