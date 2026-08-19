"""Tests smoke generados por plantilla (determinista, sin LLM)."""

import pytest

from motor.core.web.models import SearchResult, SourceMetadata, WebDocument, Citation


def test_import_models():
    """El módulo importa sin errores."""
    assert SearchResult is not None


def test_dataclass_models_SearchResult():
    """Instanciación con valores por defecto (skip si valida/requiere args)."""
    try:
        inst = SearchResult()
    except (TypeError, ValueError):
        pytest.skip('dataclass requiere argumentos o valida en __post_init__')
    assert inst is not None


def test_dataclass_models_SourceMetadata():
    """Instanciación con valores por defecto (skip si valida/requiere args)."""
    try:
        inst = SourceMetadata()
    except (TypeError, ValueError):
        pytest.skip('dataclass requiere argumentos o valida en __post_init__')
    assert inst is not None


def test_dataclass_models_WebDocument():
    """Instanciación con valores por defecto (skip si valida/requiere args)."""
    try:
        inst = WebDocument()
    except (TypeError, ValueError):
        pytest.skip('dataclass requiere argumentos o valida en __post_init__')
    assert inst is not None


def test_dataclass_models_Citation():
    """Instanciación con valores por defecto (skip si valida/requiere args)."""
    try:
        inst = Citation()
    except (TypeError, ValueError):
        pytest.skip('dataclass requiere argumentos o valida en __post_init__')
    assert inst is not None



def test_webdocument_to_dict_ramas():
    """Cobertura de ramas: campos None en to_dict."""
    doc = WebDocument(url="https://x.com", title="t", text=None, markdown=None)
    d = doc.to_dict()
    assert d["text"] == ""
    assert d["markdown"] == ""


def test_citation_to_dict_truncado():
    """Cobertura de ramas: truncado a 200 chars."""
    c = Citation(text="a" * 300, url="https://x.com", title="t", source="s")
    d = c.to_dict()
    assert len(d["text"]) == 200


def test_searchresult_to_dict():
    """Cobertura de ramas restantes de SearchResult.to_dict."""
    sr = SearchResult(title="t", url="u", snippet="s", source="src", published=None, language=None)
    d = sr.to_dict()
    assert d["title"] == "t" and d["published"] is None
