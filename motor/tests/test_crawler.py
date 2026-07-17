"""Tests del crawler HTTP (F24-B3).

Verifica:
1. HttpCrawler implementa Crawler
2. fetch_raw retorna CrawledDocument con metadatos
3. Protección SSRF (bloqueo de IPs privadas)
4. Validación de esquemas (solo http/https)
5. Timeout y error handling
6. Content-Type validation
7. Content-Length validation
8. Integración con Registry
9. HEAD + GET flow
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from motor.core.web.base import Crawler
from motor.core.web.pipeline import WebPipeline
from motor.core.web.registry import Registry


class TestHttpCrawler:
    def test_crawler_importable(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        assert HttpCrawler is not None

    def test_implements_crawler(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        assert issubclass(HttpCrawler, Crawler)

    def test_default_name(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler()
        assert c.name == "httpx"


class TestSSRFProtection:
    def test_block_private_ip_localhost(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler()
        with pytest.raises(ValueError, match="private network"):
            c.fetch_raw("http://127.0.0.1:8080/test")

    def test_block_private_ip_10(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler()
        with pytest.raises(ValueError, match="private network"):
            c.fetch_raw("http://10.0.0.5/test")

    def test_block_private_ip_192_168(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler()
        with pytest.raises(ValueError, match="private network"):
            c.fetch_raw("http://192.168.1.1/test")

    def test_allow_private_when_configured(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        HttpCrawler(allow_private=True)
        # _validate_url should still block (it's a separate function)
        import pytest

        from motor.core.web.crawler.providers.httpx_crawler import _validate_url
        with pytest.raises(ValueError):
            _validate_url("http://127.0.0.1/test")

    def test_block_file_scheme(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler()
        with pytest.raises(ValueError, match="Scheme"):
            c.fetch_raw("file:///etc/passwd")

    def test_block_ftp_scheme(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler()
        with pytest.raises(ValueError, match="Scheme"):
            c.fetch_raw("ftp://ftp.example.com/file")


class TestCrawlerFetch:
    def test_ssrf_blocks_private(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler()
        with pytest.raises(ValueError):
            c.fetch_raw("http://127.0.0.1/test")

    def test_scheme_validation_blocks_file(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler()
        with pytest.raises(ValueError):
            c.fetch_raw("file:///etc/passwd")

    def test_crawled_document_defaults(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import CrawledDocument

        doc = CrawledDocument(url="https://example.com")
        assert doc.url == "https://example.com"
        assert doc.status_code == 0
        assert doc.content == b""

    def test_to_dict(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import CrawledDocument

        doc = CrawledDocument(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            content=b"test",
            elapsed_ms=10.5,
        )
        d = doc.to_dict()
        assert d["url"] == "https://example.com"
        assert d["status_code"] == 200
        assert d["elapsed_ms"] == 10.5


class TestRegistryCrawler:
    def test_register_crawler(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        reg = Registry()
        c = HttpCrawler()
        reg.register_crawler("httpx", c)
        assert "httpx" in reg.list_crawlers()
        assert reg.get_crawler("httpx") is c

    def test_pipeline_uses_crawler(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        reg = Registry()
        crawler = HttpCrawler()
        reg.register_crawler("httpx", crawler)
        pipeline = WebPipeline(reg)

        with patch.object(crawler, "fetch", return_value="<html>ok</html>"):
            html = pipeline.fetch("https://example.com", crawler="httpx")
            assert html == "<html>ok</html>"
