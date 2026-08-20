"""Tests de cobertura para motor/core/web/cleaner/url_utils.py (gate 90%)."""

from __future__ import annotations

from motor.core.web.cleaner.url_utils import content_hash, get_document_id, normalize_url


class TestNormalizeUrl:
    def test_lowercase_scheme_host(self) -> None:
        assert normalize_url("HTTPS://Example.COM/Path/") == "https://example.com/Path"

    def test_elimina_fragmento(self) -> None:
        assert normalize_url("http://example.com/page#fragment") == "http://example.com/page"

    def test_slash_final_mantiene_raiz(self) -> None:
        assert normalize_url("http://example.com/") == "http://example.com/"

    def test_slash_final_quita_en_path(self) -> None:
        assert normalize_url("http://example.com/path/") == "http://example.com/path"

    def test_sin_path_raiz(self) -> None:
        assert normalize_url("http://example.com") == "http://example.com/"

    def test_query_mantenida(self) -> None:
        assert normalize_url("http://example.com/p?a=1#frag") == "http://example.com/p?a=1"


class TestGetDocumentId:
    def test_usa_canonical(self) -> None:
        assert get_document_id("http://x.com/1", "https://canon.example.com/doc") == "https://canon.example.com/doc"

    def test_usa_url_si_no_canonical(self) -> None:
        assert get_document_id("HTTP://X.com/Page/") == "http://x.com/Page"

    def test_canonical_vacio_usa_url(self) -> None:
        assert get_document_id("http://x.com/a", "") == "http://x.com/a"


class TestContentHash:
    def test_estable(self) -> None:
        assert content_hash("hola   mundo") == content_hash("hola mundo")

    def test_hex_sha256(self) -> None:
        h = content_hash("abc")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_distinto_texto(self) -> None:
        assert content_hash("a") != content_hash("b")
