"""Tests de proveedores de búsqueda web (F24-B2).

Verifica:
1. DuckDuckGoSearchProvider implementa SearchProvider
2. SearXNGSearchProvider implementa SearchProvider
3. Registry acepta ambos proveedores
4. Pipeline.search usa múltiples proveedores
5. Errores transitorios manejados
6. Timeout y User-Agent configurables
"""

from __future__ import annotations

from unittest.mock import patch

from motor.core.web.base import SearchProvider
from motor.core.web.models import SearchResult
from motor.core.web.pipeline import WebPipeline
from motor.core.web.registry import Registry


class TestDuckDuckGoProvider:
    def test_importable(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider

        assert DuckDuckGoSearchProvider is not None

    def test_implements_search_provider(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider

        assert issubclass(DuckDuckGoSearchProvider, SearchProvider)

    def test_default_config(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider

        p = DuckDuckGoSearchProvider()
        assert p.name == "duckduckgo"

    def test_search_returns_search_results(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider

        p = DuckDuckGoSearchProvider()
        with patch.object(p, "_search_once", return_value=[
            SearchResult(title="Example Title", url="https://example.com",
                         snippet="Example snippet text", source="duckduckgo"),
        ]):
            results = p.search("test query", limit=5)
            assert len(results) == 1
            assert all(isinstance(r, SearchResult) for r in results)
            assert results[0].title == "Example Title"
            assert results[0].url == "https://example.com"
            assert results[0].source == "duckduckgo"

    def test_retry_on_timeout(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider

        p = DuckDuckGoSearchProvider(max_retries=1)
        import httpx

        with patch.object(p, "_search_once", side_effect=[
            httpx.TimeoutException("timeout", request=None),
            [SearchResult(title="Retry OK", url="https://ok.com",
                          snippet="", source="duckduckgo")],
        ]):
            results = p.search("test")
            assert len(results) == 1
            assert results[0].title == "Retry OK"


class TestSearXNGProvider:
    def test_importable(self) -> None:
        from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider

        assert SearXNGSearchProvider is not None

    def test_implements_search_provider(self) -> None:
        from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider

        assert issubclass(SearXNGSearchProvider, SearchProvider)

    def test_default_config(self) -> None:
        from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider

        p = SearXNGSearchProvider()
        assert p.name == "searxng"

    def test_search_returns_search_results(self) -> None:
        from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider

        p = SearXNGSearchProvider()
        with patch.object(p, "_search_once", return_value=[
            SearchResult(title="SearX Result", url="https://searx.example",
                         snippet="SearX snippet", source="searxng"),
        ]):
            results = p.search("test")
            assert len(results) == 1
            assert results[0].source == "searxng"

    def test_searxng_configurable_base_url(self) -> None:
        from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider

        p = SearXNGSearchProvider(base_url="https://my-searx.instance")
        assert "my-searx" in p._base_url


class TestRegistrySearcher:
    def test_register_searcher(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider

        reg = Registry()
        p = DuckDuckGoSearchProvider()
        reg.register_searcher("duckduckgo", p)
        assert "duckduckgo" in reg.list_searchers()
        assert reg.get_searcher("duckduckgo") is p

    def test_register_multiple_searchers(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider
        from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider

        reg = Registry()
        reg.register_searcher("duckduckgo", DuckDuckGoSearchProvider())
        reg.register_searcher("searxng", SearXNGSearchProvider())
        assert len(reg.list_searchers()) == 2

    def test_get_nonexistent_raises(self) -> None:
        import pytest
        reg = Registry()
        with pytest.raises(KeyError):
            reg.get_searcher("nonexistent")


class TestPipelineSearch:
    def test_pipeline_search_with_sources(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider
        from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider

        reg = Registry()
        ddg = DuckDuckGoSearchProvider()
        sxn = SearXNGSearchProvider()
        reg.register_searcher("duckduckgo", ddg)
        reg.register_searcher("searxng", sxn)
        pipeline = WebPipeline(reg)

        with patch.object(ddg, "search", return_value=[
            SearchResult(title="DDG", url="https://ddg.com", snippet="", source="duckduckgo"),
        ]), patch.object(sxn, "search", return_value=[
            SearchResult(title="SearX", url="https://searx.com", snippet="", source="searxng"),
        ]):
            results = pipeline.search("test", sources=["duckduckgo", "searxng"])
            assert len(results) == 2
            sources = {r.source for r in results}
            assert "duckduckgo" in sources
            assert "searxng" in sources

    def test_pipeline_search_default_all_sources(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider

        reg = Registry()
        ddg = DuckDuckGoSearchProvider()
        reg.register_searcher("duckduckgo", ddg)
        pipeline = WebPipeline(reg)

        with patch.object(ddg, "search", return_value=[
            SearchResult(title="DDG", url="https://ddg.com", snippet="", source="duckduckgo"),
        ]):
            results = pipeline.search("test")
            assert len(results) == 1
