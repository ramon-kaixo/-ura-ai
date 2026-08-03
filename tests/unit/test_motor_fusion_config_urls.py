"""Tests para motor/core/fusion/config.py y motor/core/web/cleaner/url_utils.py."""
from __future__ import annotations

import hashlib

from motor.core.fusion.config import FusionConfig, make_config_hash
from motor.core.web.cleaner.url_utils import content_hash, get_document_id, normalize_url


class TestFusionConfig:
    def test_defaults(self) -> None:
        c = FusionConfig()
        assert c.enabled is True
        assert c.default_engine == "default"
        assert c.max_claims_per_document == 50
        assert c.min_confidence_threshold == 0.3
        assert c.authority_weight == 0.4
        assert c.freshness_weight == 0.3
        assert c.relevance_weight == 0.3

    def test_override(self) -> None:
        c = FusionConfig(enabled=False, max_facts_per_run=500)
        assert c.enabled is False
        assert c.max_facts_per_run == 500

    def test_to_dict(self) -> None:
        c = FusionConfig()
        d = c.to_dict()
        assert d["enabled"] is True
        assert d["authority_weight"] == 0.4

    def test_make_config_hash_determinista(self) -> None:
        h1 = make_config_hash(FusionConfig())
        h2 = make_config_hash(FusionConfig())
        assert h1 == h2
        assert len(h1) == 16

    def test_make_config_hash_difiere(self) -> None:
        h1 = make_config_hash(FusionConfig())
        h2 = make_config_hash(FusionConfig(max_facts_per_run=999))
        assert h1 != h2


class TestNormalizeUrl:
    def test_scheme_host_lowercase(self) -> None:
        assert normalize_url("HTTPS://Example.COM/Path/") == "https://example.com/Path"

    def test_quita_fragmento(self) -> None:
        assert normalize_url("http://example.com/page#fragment") == "http://example.com/page"

    def test_slash_final(self) -> None:
        assert normalize_url("http://example.com/") == "http://example.com/"

    def test_path_sin_slash(self) -> None:
        assert normalize_url("http://example.com") == "http://example.com/"

    def test_con_query(self) -> None:
        assert normalize_url("http://example.com/path?a=1&b=2#frag") == "http://example.com/path?a=1&b=2"


class TestGetDocumentId:
    def test_sin_canonical(self) -> None:
        assert get_document_id("HTTP://EXAMPLE.com/Page/") == "http://example.com/Page"

    def test_con_canonical(self) -> None:
        assert get_document_id("http://x.com/a", "http://canonical.com/b") == "http://canonical.com/b"


class TestContentHash:
    def test_normaliza_espacios(self) -> None:
        assert content_hash("hola   mundo") == content_hash("hola mundo")

    def test_determinista(self) -> None:
        assert content_hash("texto") == content_hash("texto")

    def test_valor_esperado(self) -> None:
        expected = hashlib.sha256(b"abc").hexdigest()
        assert content_hash("abc") == expected

    def test_diferente_texto(self) -> None:
        assert content_hash("a") != content_hash("b")
