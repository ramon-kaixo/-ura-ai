"""Cobertura 100x100 de motor/core/web/base.py (TASK-20260815-003).

base.py define los contratos ABC del módulo Web Intelligence. Los cuerpos
abstractos (líneas `...`) solo se ejecutan cuando una subclase concreta
delega en super(); los tests lo ejercitan mediante subclases que reenvían
cada miembro abstracto a su implementación base.

Sin dependencias externas: solo el paquete motor.core.web + stdlib.
"""

from __future__ import annotations

from typing import Any

import pytest

from motor.core.web.base import Crawler, Extractor, Ranker, SearchProvider, SourceValidator, Summarizer


class _ConcreteSearchProvider(SearchProvider):
    """SearchProvider concreto que delega en los cuerpos abstractos."""

    @property
    def name(self) -> str:
        return super().name  # type: ignore[no-any-return]

    def search(self, query: str, limit: int = 10) -> list[Any]:
        return super().search(query, limit)  # type: ignore[no-any-return]


class _ConcreteCrawler(Crawler):
    """Crawler concreto que delega en los cuerpos abstractos."""

    @property
    def name(self) -> str:
        return super().name  # type: ignore[no-any-return]

    def fetch(self, url: str, timeout: int = 30) -> str:
        return super().fetch(url, timeout)  # type: ignore[no-any-return]


class _ConcreteExtractor(Extractor):
    """Extractor concreto que delega en los cuerpos abstractos."""

    @property
    def name(self) -> str:
        return super().name  # type: ignore[no-any-return]

    def extract(self, html: str, url: str) -> Any:
        return super().extract(html, url)

    def extract_text(self, html: str) -> str:
        return super().extract_text(html)  # type: ignore[no-any-return]


class _ConcreteRanker(Ranker):
    """Ranker concreto que delega en el cuerpo abstracto."""

    def rank(self, results: list[Any], query: str) -> list[Any]:
        return super().rank(results, query)  # type: ignore[no-any-return]


class _ConcreteSummarizer(Summarizer):
    """Summarizer concreto que delega en el cuerpo abstracto."""

    def summarize(self, query: str, documents: list[Any]) -> tuple[Any, list[Any]]:
        return super().summarize(query, documents)  # type: ignore[no-any-return]


class _ConcreteValidator(SourceValidator):
    """SourceValidator concreto que delega en los cuerpos abstractos."""

    def validate(self, url: str, document: Any = None) -> float:
        return super().validate(url, document)  # type: ignore[no-any-return]

    def is_blocked(self, url: str) -> bool:
        return super().is_blocked(url)  # type: ignore[no-any-return]


class TestSearchProvider:
    """Contrato SearchProvider."""

    def test_es_abstracta(self) -> None:
        with pytest.raises(TypeError):
            SearchProvider()  # type: ignore[abstract]

    def test_name_delega_en_base(self) -> None:
        assert _ConcreteSearchProvider().name is None

    def test_search_delega_en_base(self) -> None:
        assert _ConcreteSearchProvider().search("q", limit=5) is None

    def test_name_default_limit(self) -> None:
        assert _ConcreteSearchProvider().search("q") is None


class TestCrawler:
    """Contrato Crawler."""

    def test_es_abstracta(self) -> None:
        with pytest.raises(TypeError):
            Crawler()  # type: ignore[abstract]

    def test_name_delega_en_base(self) -> None:
        assert _ConcreteCrawler().name is None

    def test_fetch_delega_en_base(self) -> None:
        assert _ConcreteCrawler().fetch("https://example.com") is None

    def test_fetch_timeout_explicito(self) -> None:
        assert _ConcreteCrawler().fetch("https://example.com", timeout=5) is None


class TestExtractor:
    """Contrato Extractor."""

    def test_es_abstracta(self) -> None:
        with pytest.raises(TypeError):
            Extractor()  # type: ignore[abstract]

    def test_name_delega_en_base(self) -> None:
        assert _ConcreteExtractor().name is None

    def test_extract_delega_en_base(self) -> None:
        assert _ConcreteExtractor().extract("<html></html>", "https://example.com") is None

    def test_extract_text_delega_en_base(self) -> None:
        assert _ConcreteExtractor().extract_text("<html></html>") is None


class TestRanker:
    """Contrato Ranker."""

    def test_es_abstracta(self) -> None:
        with pytest.raises(TypeError):
            Ranker()  # type: ignore[abstract]

    def test_rank_delega_en_base(self) -> None:
        assert _ConcreteRanker().rank([], "q") is None


class TestSummarizer:
    """Contrato Summarizer."""

    def test_es_abstracta(self) -> None:
        with pytest.raises(TypeError):
            Summarizer()  # type: ignore[abstract]

    def test_summarize_delega_en_base(self) -> None:
        assert _ConcreteSummarizer().summarize("q", []) is None


class TestSourceValidator:
    """Contrato SourceValidator."""

    def test_es_abstracta(self) -> None:
        with pytest.raises(TypeError):
            SourceValidator()  # type: ignore[abstract]

    def test_validate_delega_en_base(self) -> None:
        assert _ConcreteValidator().validate("https://example.com") is None

    def test_validate_con_documento(self) -> None:
        assert _ConcreteValidator().validate("https://example.com", document="doc") is None

    def test_is_blocked_delega_en_base(self) -> None:
        assert _ConcreteValidator().is_blocked("https://example.com") is None
