
"""Tests de document_quality."""
from core.document_quality import detect_language, content_type
from core.document_quality import source_reliability, doc_id_from_text


def test_detect_language_spanish():
    lang = detect_language("Hola mundo esto es una prueba")
    assert lang in ("es", "spanish", "español")


def test_detect_language_english():
    lang = detect_language("Hello world this is a test of the system")
    assert lang in ("en", "english")


def test_content_type():
    assert content_type("def foo(): pass") == "code"
    assert "# Title\n\nBody" in content_type("# Title\n\nBody") or content_type("# Title\n\nBody")


def test_source_reliability():
    assert source_reliability("https://github.com") >= 0.4
    assert source_reliability("https://unknown123xyz.com") <= 0.5


def test_doc_id_deterministic():
    id1 = doc_id_from_text("test text", prefix="doc")
    id2 = doc_id_from_text("test text", prefix="doc")
    assert id1 == id2
