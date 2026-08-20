"""Cobertura 100x100 de motor/core/web/extractor/providers/html_extractor.py
(TASK-20260815-003).

Cubre detect_encoding (BOM, meta charset, XML encoding, content-type,
fallback), extract_metadata (orden name/content, publish_time, canonical,
aplicación de contenido), HtmlExtractor.extract/extract_text y las ramas del
parser HTML (tags skip anidados, tags bloque, datos con whitespace).

Sin dependencias externas: stdlib (html.parser, re) + motor.core.web.
"""

from __future__ import annotations

from motor.core.web.extractor.providers.html_extractor import (
    HtmlExtractor,
    _clean_html,
    _HtmlCleaner,
    _parse_attrs,
    _to_webdocument,
    detect_encoding,
    extract_metadata,
)


class TestDetectEncoding:
    """Detección de codificación."""

    def test_bom_utf8_sig(self) -> None:
        assert detect_encoding(b"\xef\xbb\xbf<html>") == "utf-8-sig"

    def test_meta_charset(self) -> None:
        html = b'<html><head><meta charset="iso-8859-1"></head></html>'
        assert detect_encoding(html) == "iso-8859-1"

    def test_meta_charset_single_quote(self) -> None:
        html = b"<meta charset='utf-16'>"
        assert detect_encoding(html) == "utf-16"

    def test_meta_charset_sin_quotes(self) -> None:
        html = b"<meta charset=windows-1252>"
        assert detect_encoding(html) == "windows-1252"

    def test_xml_encoding(self) -> None:
        html = b'<?xml version="1.0" encoding="ISO-8859-15"?>'
        assert detect_encoding(html) == "iso-8859-15"

    def test_content_type(self) -> None:
        assert detect_encoding(b"<html></html>", content_type="text/html; charset=utf-16") == "utf-16"

    def test_content_type_sin_charset_fallback(self) -> None:
        assert detect_encoding(b"<html></html>", content_type="text/html") == "utf-8"

    def test_fallback_utf8(self) -> None:
        assert detect_encoding(b"<html></html>") == "utf-8"

    def test_meta_despues_de_2048_bytes_no_detecta(self) -> None:
        body = b"a" * 2050
        html = body + b'<meta charset="utf-7">'
        assert detect_encoding(html) == "utf-8"


class TestExtractMetadata:
    """Metadatos básicos desde meta/link."""

    def test_meta_name(self) -> None:
        html = '<meta name="author" content="Ana">'
        assert extract_metadata(html)["author"] == "Ana"

    def test_meta_property_con_dos_puntos(self) -> None:
        html = '<meta property="og:type" content="article">'
        assert extract_metadata(html)["og_type"] == "article"

    def test_meta_content_primero(self) -> None:
        html = '<meta content="Desc" name="description">'
        assert extract_metadata(html)["description"] == "Desc"

    def test_meta_content_primero_no_sobreescribe(self) -> None:
        html = '<meta name="author" content="Primero"><meta content="Segundo" name="author">'
        assert extract_metadata(html)["author"] == "Primero"

    def test_published_time(self) -> None:
        html = '<meta property="article:published_time" content="2026-01-01">'
        meta = extract_metadata(html)
        assert meta["published_time"] == "2026-01-01"
        assert meta["article_published_time"] == "2026-01-01"

    def test_published_time_primera_coincidencia(self) -> None:
        html = (
            '<meta property="article:published_time" content="2026-01-01">'
            '<meta name="published_time" content="2025-01-01">'
        )
        assert extract_metadata(html)["published_time"] == "2026-01-01"

    def test_canonical(self) -> None:
        html = '<link rel="canonical" href="https://example.com/canon">'
        assert extract_metadata(html)["canonical_url"] == "https://example.com/canon"

    def test_vacio(self) -> None:
        assert extract_metadata("<html></html>") == {}

    def test_sin_meta_no_vacios(self) -> None:
        html = '<meta name="x">'
        meta = extract_metadata(html)
        assert "x" not in meta or meta["x"] == ""


class TestParseAttrs:
    """Parsing de atributos (descarta valores None)."""

    def test_filtra_none(self) -> None:
        assert _parse_attrs([("a", "1"), ("b", None), ("c", "3")]) == {"a": "1", "c": "3"}

    def test_vacio(self) -> None:
        assert _parse_attrs([]) == {}


class TestCleanHtml:
    """Limpieza DOM → texto plano."""

    def test_extrae_texto_y_bloques(self) -> None:
        html = "<p>Hola</p><div>mundo</div>"
        assert _clean_html(html) == "Hola\nmundo"

    def test_elimina_script_style(self) -> None:
        html = "<script>var x=1;</script><p>texto</p><style>a{}</style>"
        assert _clean_html(html) == "texto"

    def test_elimina_skip_tags_anidados(self) -> None:
        html = "<nav><p>nav1</p><nav><p>nav2</p></nav><p>nav3</p></nav><p>visible</p>"
        assert _clean_html(html) == "visible"

    def test_normaliza_whitespace(self) -> None:
        assert _clean_html("<p>a   b\t c</p>") == "a b c"

    def test_colapsa_multiples_newlines(self) -> None:
        html = "<p>a</p><p>b</p><p>c</p>"
        assert _clean_html(html) == "a\nb\nc"

    def test_vacio(self) -> None:
        assert _clean_html("") == ""

    def test_data_antes_de_bloque_no_duplica_newline(self) -> None:
        html = "texto<br>"
        assert _clean_html(html) == "texto"

    def test_endtag_skip_sin_apertura_no_decrementa(self) -> None:
        c = _HtmlCleaner()
        c.feed("</script>texto")
        assert c.get_text() == "texto"

    def test_data_vacia_ignorada(self) -> None:
        c = _HtmlCleaner()
        c.handle_data("")
        assert c.get_text() == ""


class TestToWebdocument:
    """Construcción de WebDocument."""

    def test_con_titulo(self) -> None:
        html = "<title>Mi Título</title><meta name=\"author\" content=\"Ana\"><p>hola mundo</p>"
        doc = _to_webdocument(html, "https://example.com/a", "hola mundo", 0.0)
        assert doc.title == "Mi Título"
        assert doc.url == "https://example.com/a"
        assert doc.word_count == 2
        assert doc.quality_score > 0
        assert doc.metadata["author"] == "Ana"
        assert doc.metadata["extractor"] == "html"

    def test_sin_titulo(self) -> None:
        doc = _to_webdocument("<p>texto</p>", "https://example.com/a", "texto", 0.0)
        assert doc.title == ""

    def test_texto_vacio(self) -> None:
        doc = _to_webdocument("<p></p>", "https://example.com/a", "", 0.0)
        assert doc.word_count == 0
        assert doc.quality_score == 0.0

    def test_metadata_completa(self) -> None:
        html = (
            "<meta name='description' content='desc'>"
            "<meta property='article:published_time' content='2026-01-01'>"
            "<link rel='canonical' href='https://canon'>"
            "<html lang='es'>"
        )
        doc = _to_webdocument(html, "https://example.com/a", "texto", 0.0)
        assert doc.metadata["description"] == "desc"
        assert doc.metadata["published_time"] == "2026-01-01"
        assert doc.metadata["canonical_url"] == "https://canon"

    def test_quality_saturada_a_uno(self) -> None:
        doc = _to_webdocument("<p>t</p>", "https://example.com/a", "palabra " * 600, 0.0)
        assert doc.quality_score == 1.0


class TestHtmlExtractor:
    """Extractor público."""

    def test_name(self) -> None:
        assert HtmlExtractor().name == "html"

    def test_extract_text(self) -> None:
        assert HtmlExtractor().extract_text("<p>hola</p>") == "hola"

    def test_extract(self) -> None:
        html = "<title>T</title><p>hola mundo</p>"
        doc = HtmlExtractor().extract(html, "https://example.com/a")
        assert doc.title == "T"
        assert doc.text == "T\nhola mundo"  # el título se incluye en el texto
        assert doc.url == "https://example.com/a"
        assert doc.metadata["extraction_time_ms"] >= 0

    def test_extract_sin_metadata_estructura(self) -> None:
        doc = HtmlExtractor().extract("<p>solo texto</p>", "https://example.com/a")
        assert doc.metadata["author"] is None
        assert doc.metadata["description"] is None
        assert doc.metadata["language"] is None
        assert doc.metadata["canonical_url"] is None
