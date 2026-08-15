"""Cobertura 100x100 de motor/core/web/models.py (TASK-20260815-003).

Cubre los three dataclasses + to_dict con ramas de texto vacío/presente
(SearchResult, SourceMetadata, WebDocument, Citation).

Sin dependencias externas: solo motor.core.web + stdlib.
"""

from __future__ import annotations

from motor.core.web.models import Citation, SearchResult, SourceMetadata, WebDocument


class TestSearchResult:
    """Resultado de búsqueda."""

    def test_to_dict(self) -> None:
        r = SearchResult(title="T", url="https://example.com/a", snippet="S", source="ddg", score=0.7)
        d = r.to_dict()
        assert d == {
            "title": "T",
            "url": "https://example.com/a",
            "snippet": "S",
            "source": "ddg",
            "score": 0.7,
            "published": None,
        }

    def test_to_dict_con_published(self) -> None:
        r = SearchResult(title="T", url="u", snippet="s", source="x", published="2026-01-01")
        assert r.to_dict()["published"] == "2026-01-01"

    def test_defaults(self) -> None:
        r = SearchResult(title="T", url="u", snippet="s", source="x")
        assert r.score == 0.0
        assert r.published is None
        assert r.language is None


class TestSourceMetadata:
    """Metadatos de fuente."""

    def test_defaults(self) -> None:
        m = SourceMetadata(url="https://example.com/a", domain="example.com")
        assert m.fetch_time_ms == 0.0
        assert m.content_type is None
        assert m.content_length == 0
        assert m.status_code == 200
        assert m.error is None

    def test_con_valores(self) -> None:
        m = SourceMetadata(
            url="https://example.com/a",
            domain="example.com",
            status_code=404,
            error="not found",
        )
        assert m.status_code == 404
        assert m.error == "not found"


class TestWebDocument:
    """Documento web extraído."""

    def test_to_dict_con_texto(self) -> None:
        doc = WebDocument(url="u", title="T", text="x" * 600, markdown="m" * 500, word_count=600)
        d = doc.to_dict()
        assert d["text"] == "x" * 500
        assert d["markdown"] == "m" * 500
        assert d["word_count"] == 600
        assert d["language"] is None
        assert d["quality_score"] == 1.0

    def test_to_dict_sin_texto(self) -> None:
        doc = WebDocument(url="u", title="T")
        d = doc.to_dict()
        assert d["text"] == ""
        assert d["markdown"] == ""
        assert d["word_count"] == 0

    def test_to_dict_language(self) -> None:
        doc = WebDocument(url="u", title="T", text="a", language="es")
        assert doc.to_dict()["language"] == "es"

    def test_extracted_at_por_defecto(self) -> None:
        doc = WebDocument(url="u", title="T")
        assert doc.extracted_at > 0

    def test_dataclass_fields_predeterminados(self) -> None:
        doc = WebDocument(url="u", title="T")
        assert doc.html == ""
        assert doc.text == ""
        assert doc.metadata is None
        assert doc.readability_score == 0.0
        assert doc.word_count == 0
        assert doc.quality_score == 1.0


class TestCitation:
    """Cita."""

    def test_to_dict(self) -> None:
        c = Citation(text="t" * 300, url="https://example.com/a", title="T", source="s")
        d = c.to_dict()
        assert d["text"] == "t" * 200
        assert d["url"] == "https://example.com/a"
        assert d["title"] == "T"
        assert d["source"] == "s"
        assert d["confidence"] == 1.0

    def test_to_dict_confianza_custom(self) -> None:
        c = Citation(text="a", url="u", title="t", source="s", confidence=0.5)
        assert c.to_dict()["confidence"] == 0.5

    def test_defaults(self) -> None:
        c = Citation(text="a", url="u", title="t", source="s")
        assert c.fragment == ""
        assert c.confidence == 1.0
        assert c.timestamp > 0
