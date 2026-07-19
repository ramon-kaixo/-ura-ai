"""Tests del extractor HTML (F24-B4)."""

from __future__ import annotations

from motor.core.web.base import Extractor
from motor.core.web.models import WebDocument
from motor.core.web.registry import Registry

SIMPLE_HTML = """<!DOCTYPE html>
<html><head>
<title>Test Page</title>
<meta name="description" content="A test page">
<meta name="author" content="Test Author">
<meta name="language" content="en">
<link rel="canonical" href="https://example.com/canonical">
</head><body>
<p>Hello world. This is a test paragraph.</p>
<script>alert('should be removed');</script>
<style>.css{display:none}</style>
<noscript>no JS fallback</noscript>
</body></html>"""

SCRIPT_HTML = """<html><head><title>Script test</title></head><body>
<p>Visible text</p>
<script>var x = 1;</script>
<p>After script</p>
</body></html>"""

META_CHARSET_HTML = (
    '<html><head><meta charset="iso-8859-1"><title>Charset test</title>'
    "</head><body><p>café</p></body></html>"
)

MINIMAL_HTML = "<html><head></head><body><p>Hello</p></body></html>"


class TestHtmlExtractor:
    def test_importable(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        assert HtmlExtractor is not None

    def test_implements_extractor(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        assert issubclass(HtmlExtractor, Extractor)

    def test_name(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        assert HtmlExtractor().name == "html"


class TestExtraction:
    def test_title(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(SIMPLE_HTML, "https://example.com")
        assert doc.title == "Test Page"

    def test_text_content(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(SIMPLE_HTML, "https://example.com")
        assert "Hello world" in doc.text
        assert "test paragraph" in doc.text

    def test_scripts_removed(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(SCRIPT_HTML, "https://example.com")
        assert "Visible text" in doc.text
        assert "After script" in doc.text
        assert "var x = 1" not in doc.text

    def test_styles_removed(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(SIMPLE_HTML, "https://example.com")
        assert "display:none" not in doc.text
        assert ".css" not in doc.text

    def test_canonical_url(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import extract_metadata

        meta = extract_metadata(SIMPLE_HTML)
        assert meta.get("canonical_url") == "https://example.com/canonical"

    def test_author(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import extract_metadata

        meta = extract_metadata(SIMPLE_HTML)
        assert meta.get("author") == "Test Author"

    def test_description(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import extract_metadata

        meta = extract_metadata(SIMPLE_HTML)
        assert meta.get("description") == "A test page"

    def test_language(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import extract_metadata

        meta = extract_metadata(SIMPLE_HTML)
        assert meta.get("language") == "en"

    def test_minimal_html(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(MINIMAL_HTML, "https://example.com")
        assert isinstance(doc, WebDocument)
        assert doc.text == "Hello"

    def test_word_count(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(SIMPLE_HTML, "https://example.com")
        assert doc.word_count > 0

    def test_returns_webdocument(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(SIMPLE_HTML, "https://example.com")
        assert isinstance(doc, WebDocument)
        assert doc.url == "https://example.com"

    def test_extract_text(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        text = HtmlExtractor().extract_text(SIMPLE_HTML)
        assert "Hello world" in text

    def test_noscript_removed(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(SIMPLE_HTML, "https://example.com")
        assert "no JS fallback" not in doc.text


class TestDetectEncoding:
    def test_utf8_bom(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import detect_encoding

        assert detect_encoding(b"\xef\xbb\xbf<html></html>") == "utf-8-sig"

    def test_meta_charset(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import detect_encoding

        html = b'<html><head><meta charset="iso-8859-1"></head></html>'
        assert detect_encoding(html) == "iso-8859-1"

    def test_default_utf8(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import detect_encoding

        assert detect_encoding(b"<html></html>") == "utf-8"

    def test_xml_encoding(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import detect_encoding

        html = b'<?xml version="1.0" encoding="windows-1252"?><html></html>'
        assert detect_encoding(html) == "windows-1252"


class TestEmptyMalformed:
    def test_empty_html(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract("", "https://example.com")
        assert isinstance(doc, WebDocument)
        assert doc.text == ""

    def test_malformed_html(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract("<p>unclosed<p>another", "https://example.com")
        assert isinstance(doc, WebDocument)
        assert "unclosed" in doc.text
        assert "another" in doc.text


class TestRegistryExtractor:
    def test_register_extractor(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        reg = Registry()
        e = HtmlExtractor()
        reg.register_extractor("html", e)
        assert "html" in reg.list_extractors()
        assert reg.get_extractor("html") is e

    def test_pipeline_uses_extractor(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        reg = Registry()
        extractor = HtmlExtractor()
        reg.register_extractor("html", extractor)
        from motor.core.web.pipeline import WebPipeline

        pipeline = WebPipeline(reg)
        doc = pipeline.extract(
            "<html><body><p>test</p></body></html>",
            "https://example.com",
            extractor="html",
        )
        assert doc.text == "test"


class TestQualityScore:
    def test_good_content_scores_high(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        long_html = (
            "<html><head><title>Good</title></head><body>"
            + "<p>word</p>" * 200
            + "</body></html>"
        )
        doc = HtmlExtractor().extract(long_html, "https://example.com")
        assert doc.quality_score >= 0.3

    def test_empty_content_scores_low(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract(
            "<html><body></body></html>", "https://example.com"
        )
        assert doc.quality_score < 0.5
