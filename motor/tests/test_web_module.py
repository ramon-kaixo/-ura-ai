"""Cobertura 100x100 del módulo Web Intelligence (TASK-20260814-001).

Cubre modelos, config, registry, pipeline, y todos los proveedores
(crawler, extractor, ranker, searchers, summarizer, cleaner, citation)
con mocks de red (httpx) y fakes registrados en el Registry.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from motor.core.web.base import Crawler, Extractor, Ranker, SearchProvider, SourceValidator, Summarizer
from motor.core.web.models import Citation, SearchResult, WebDocument


class TestModelsWeb:
    def test_search_result_to_dict(self) -> None:
        r = SearchResult(title="t", url="u", snippet="s", source="x", score=1.0, published="p", language="es")
        d = r.to_dict()
        assert d["title"] == "t" and d["url"] == "u" and d["score"] == 1.0 and d["published"] == "p"
        assert "language" not in d

    def test_web_document_to_dict(self) -> None:
        from motor.core.web.models import SourceMetadata

        doc = WebDocument(
            url="u",
            title="t",
            text="x" * 600,
            markdown="m" * 600,
            word_count=100,
            language="es",
            quality_score=0.5,
            metadata=SourceMetadata(url="u", domain="d"),
        )
        d = doc.to_dict()
        assert d["text"] == "x" * 500 and d["markdown"] == "m" * 500
        assert d["word_count"] == 100 and d["language"] == "es" and d["quality_score"] == 0.5

    def test_citation_to_dict(self) -> None:
        c = Citation(text="a" * 300, url="u", title="t", source="s", confidence=0.8)
        d = c.to_dict()
        assert d["text"] == "a" * 200 and d["confidence"] == 0.8 and d["title"] == "t"

    def test_source_metadata(self) -> None:
        from motor.core.web.models import SourceMetadata

        m = SourceMetadata(url="u", domain="d", error="e")
        assert m.status_code == 200 and m.error == "e"


class TestWebConfig:
    def test_defaults(self) -> None:
        from motor.core.web.config import WebConfig

        c = WebConfig()
        assert c.default_searcher == "duckduckgo"
        assert c.search_timeout == 10
        assert c.max_results_per_source == 10
        assert c.respect_robots_txt is True
        assert "URA/1.0" in c.user_agent

    def test_override(self) -> None:
        from motor.core.web.config import WebConfig

        c = WebConfig(
            {
                "default_searcher": "searxng",
                "search_timeout": "25",
                "max_documents_to_summarize": 3,
                "respect_robots_txt": False,
            }
        )
        assert c.default_searcher == "searxng"
        assert c.search_timeout == 25
        assert c.max_documents_to_summarize == 3
        assert c.respect_robots_txt is False
        assert c.robots_txt_cache_ttl == 3600


class FakeSearchProvider(SearchProvider):
    name = "fake-searcher"

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or []

    @property
    def _name(self) -> str:
        return self.name

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        return self._results


class FakeCrawler(Crawler):
    def __init__(self, html: str = "<html>ok</html>", error: Exception | None = None) -> None:
        self._html = html
        self._error = error

    @property
    def name(self) -> str:
        return "fake-crawler"

    def fetch(self, url: str, timeout: int = 30) -> str:
        if self._error:
            raise self._error
        return self._html


class FakeExtractor(Extractor):
    @property
    def name(self) -> str:
        return "fake-extractor"

    def extract(self, html: str, url: str) -> WebDocument:
        return WebDocument(url=url, title="t", text="texto de prueba suficientemente largo para limpiar")

    def extract_text(self, html: str) -> str:
        return "texto"


class FakeRanker(Ranker):
    def rank(self, results: list[SearchResult], query: str) -> list[SearchResult]:
        return results


class FakeSummarizer(Summarizer):
    def summarize(self, query: str, documents: list[WebDocument]) -> tuple[str, list[Citation]]:
        return (
            "resumen",
            [Citation(text="cita", url=documents[0].url, title="t", source="s")],
        )


class FakeValidator(SourceValidator):
    def validate(self, url: str, document: WebDocument | None = None) -> float:
        return 1.0

    def is_blocked(self, url: str) -> bool:
        return False


class TestRegistryWeb:
    def test_full_lifecycle(self) -> None:
        from motor.core.web.registry import Registry

        reg = Registry()
        sr, cr, ex, rk, sm, va = (
            FakeSearchProvider(),
            FakeCrawler(),
            FakeExtractor(),
            FakeRanker(),
            FakeSummarizer(),
            FakeValidator(),
        )
        reg.register_searcher("s", sr)
        reg.register_crawler("c", cr)
        reg.register_extractor("e", ex)
        reg.register_ranker("r", rk)
        reg.register_summarizer("m", sm)
        reg.register_validator("v", va)
        assert reg.get_searcher("s") is sr
        assert reg.get_crawler("c") is cr
        assert reg.get_extractor("e") is ex
        assert reg.get_ranker("r") is rk
        assert reg.get_summarizer("m") is sm
        assert reg.get_validator("v") is va
        assert reg.list_searchers() == ["s"]
        assert reg.list_crawlers() == ["c"]
        assert reg.list_extractors() == ["e"]
        assert reg.list_rankers() == ["r"]
        assert reg.list_summarizers() == ["m"]
        assert reg.list_validators() == ["v"]

    def test_key_errors(self) -> None:
        from motor.core.web.registry import Registry

        reg = Registry()
        for getter in (
            reg.get_searcher,
            reg.get_crawler,
            reg.get_extractor,
            reg.get_ranker,
            reg.get_summarizer,
            reg.get_validator,
        ):
            with pytest.raises(KeyError):
                getter("missing")


class TestCrawlerHttpx:
    def test_validate_url_scheme(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import _validate_url

        with pytest.raises(ValueError):
            _validate_url("ftp://example.com/x")
        with pytest.raises(ValueError):
            _validate_url("file:///etc/passwd")

    def test_is_private_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import _is_private_url

        monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.1.1", 0))])
        assert _is_private_url("http://host.local/x") is True
        monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 0))])
        assert _is_private_url("http://host.public/x") is False
        monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
        assert _is_private_url("http://host.unresolvable/x") is False
        assert _is_private_url("not-a-url") is True

    def test_validate_url_private(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import _validate_url

        with pytest.raises(ValueError):
            _validate_url("http://127.0.0.1/private")

    def test_extract_charset(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import _extract_charset

        assert _extract_charset("text/html; charset=UTF-8") == "utf-8"
        assert _extract_charset("text/html; charset=ISO-8859-1; boundary=x") == "iso-8859-1"
        assert _extract_charset("text/html") == ""

    def test_crawled_document_to_dict(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import CrawledDocument

        d = CrawledDocument(url="u", elapsed_ms=1.5, error="e").to_dict()
        assert d["elapsed_ms"] == 1.5 and d["error"] == "e" and d["url"] == "u"

    def _crawler_with_fake_client(
        self,
        monkeypatch: pytest.MonkeyPatch,
        head: dict[str, Any] | None = None,
        get: dict[str, Any] | None = None,
        raise_head: Exception | None = None,
        raise_get: Exception | None = None,
    ):
        from motor.core.web.crawler.providers import httpx_crawler as mod

        class FakeResponse:
            def __init__(
                self, status_code: int, headers: dict[str, str], content: bytes = b"", url: str = "http://final/x"
            ) -> None:
                self.status_code = status_code
                self.headers = headers
                self.content = content
                self.url = url

        class FakeClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def head(self, url: str) -> FakeResponse:
                if raise_head:
                    raise raise_head
                return FakeResponse(
                    head.get("status", 200), head.get("headers", {"content-type": "text/html; charset=utf-8"})
                )

            def get(self, url: str) -> FakeResponse:
                if raise_get:
                    raise raise_get
                return FakeResponse(
                    get.get("status", 200),
                    get.get("headers", {"content-type": "text/html; charset=utf-8"}),
                    get.get("content", b"<html>ok</html>"),
                    get.get("url", "http://final/x"),
                )

        monkeypatch.setattr(mod.httpx, "Client", FakeClient)
        return mod.HttpCrawler(max_size=1024)

    def test_fetch_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:

        c = self._crawler_with_fake_client(
            monkeypatch,
            head={"headers": {"content-type": "text/html; charset=utf-8"}},
            get={"headers": {"content-type": "text/html; charset=utf-8"}},
        )
        assert c.name == "httpx"
        doc = c.fetch_raw("http://public.example/x")
        assert doc.status_code == 200
        assert doc.content == b"<html>ok</html>"
        assert doc.final_url == "http://final/x"
        assert doc.elapsed_ms >= 0

    def test_fetch_size_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._crawler_with_fake_client(
            monkeypatch,
            head={"headers": {"content-type": "text/html", "content-length": "5000"}},
            get={"headers": {"content-type": "text/html"}, "content": b"x" * 5000},
        )
        doc = c.fetch_raw("http://public.example/x")
        assert doc.error and "exceeds" in doc.error
        assert doc.content == b""

    def test_fetch_allowed_content_types(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler(allowed_content_types=["text/html"], max_size=1024)

        class FakeRes:
            def __init__(self) -> None:
                self.status_code = 200
                self.headers = {"content-type": "application/pdf"}

        class FakeClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def head(self, url: str) -> FakeRes:
                return FakeRes()

        monkeypatch.setattr("motor.core.web.crawler.providers.httpx_crawler.httpx.Client", FakeClient)
        doc = c.fetch_raw("http://public.example/x")
        assert doc.error and "not in allowed list" in doc.error

    def test_fetch_head_error_stops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._crawler_with_fake_client(monkeypatch, head={"status": 404, "headers": {"content-type": "text/html"}})
        doc = c.fetch_raw("http://public.example/x")
        assert doc.status_code == 404

    def test_fetch_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._crawler_with_fake_client(monkeypatch, raise_head=httpx.TimeoutException("t"))
        assert c.fetch_raw("http://public.example/x").error == "timeout"
        c = self._crawler_with_fake_client(monkeypatch, raise_head=httpx.TooManyRedirects("r"))
        assert c.fetch_raw("http://public.example/x").error == "too_many_redirects"
        c = self._crawler_with_fake_client(monkeypatch, raise_head=httpx.ConnectError("c"))
        assert (
            "request_error" in c.fetch_raw("http://public.example/x").error
            or "request_error" in c.fetch_raw("http://public.example/x").error
        )
        c = self._crawler_with_fake_client(monkeypatch, raise_head=ValueError("v"))
        assert c.fetch_raw("http://public.example/x").error == "v"
        c = self._crawler_with_fake_client(monkeypatch, raise_head=RuntimeError("unexp"))
        assert "unexpected" in c.fetch_raw("http://public.example/x").error

    def test_fetch_private_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

        c = HttpCrawler(allow_private=True, max_size=1024)
        monkeypatch.setattr("motor.core.web.crawler.providers.httpx_crawler.httpx.Client", FakeClientForHead)
        assert c.fetch("http://127.0.0.1/x") == "<html>ok</html>"

    def test_fetch_decode_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._crawler_with_fake_client(
            monkeypatch,
            head={"headers": {"content-type": "text/html; charset=utf-8"}},
            get={"headers": {"content-type": "text/html; charset=bad-charset"}, "content": b"\xff\xfeabc"},
        )
        assert isinstance(c.fetch("http://public.example/x"), str)

    def test_fetch_error_raises_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._crawler_with_fake_client(monkeypatch, raise_head=httpx.TimeoutException("t"))
        with pytest.raises(RuntimeError):
            c.fetch("http://public.example/x")


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content: bytes = b"<html>ok</html>",
        url: str = "http://final/x",
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}
        self.content = content
        self.url = url
        self.text = content.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err", request=httpx.Request("GET", "http://x"), response=httpx.Response(self.status_code)
            )


class FakeJsonResponse(FakeResponse):
    def json(self) -> dict[str, Any]:
        return {"results": [{"title": "T", "url": "http://u", "content": "C", "publishedDate": "2026-01-01"}]}


class FakeClientForHead:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def head(self, url: str) -> FakeResponse:
        return FakeResponse()

    def get(self, url: str) -> FakeResponse:
        return FakeResponse()


class TestExtractorHtml:
    def test_detect_encoding(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import detect_encoding

        assert detect_encoding(b"\xef\xbb\xbf<h1>") == "utf-8-sig"
        assert detect_encoding(b'<meta charset="windows-1252">') == "windows-1252"
        assert detect_encoding(b'<?xml version="1.0" encoding="ISO-8859-1"?>') == "iso-8859-1"
        assert detect_encoding(b"<html>", "text/html; charset=utf-16") == "utf-16"
        assert detect_encoding(b"<html>") == "utf-8"

    def test_extract_metadata(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import extract_metadata

        html = (
            "<html><head>"
            '<meta name="author" content="Ana">'
            '<meta content="desc" property="og:description">'
            '<meta property="article:published_time" content="2026-01-01">'
            '<link rel="canonical" href="https://example.com/final">'
            "</head></html>"
        )
        m = extract_metadata(html)
        assert m["author"] == "Ana"
        assert m["og_description"] == "desc"
        assert m["published_time"] == "2026-01-01"
        assert m["canonical_url"] == "https://example.com/final"
        assert extract_metadata("<html></html>") == {}

    def test_clean_html(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import _clean_html

        html = "<html><head><script>var x=1;</script><style>p{}</style></head><body><h1>Titulo</h1><p>Hola   mundo</p><nav>nav</nav><div>fin</div></body></html>"
        text = _clean_html(html)
        assert "Titulo" in text and "Hola mundo" in text
        assert "var x" not in text and "nav" not in text
        assert text.endswith("fin")

    def test_extract_document(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        html = (
            "<html><head><title>Mi Pagina</title></head><body><p>" + " ".join(["palabra"] * 700) + "</p></body></html>"
        )
        e = HtmlExtractor()
        assert e.name == "html"
        doc = e.extract(html, "https://example.com/a")
        assert doc.title == "Mi Pagina"
        assert doc.word_count == 702
        assert doc.quality_score == 1.0
        assert doc.metadata["canonical_url"] is None  # type: ignore[index]
        assert isinstance(e.extract_text("<p>hola</p>"), str)

    def test_extract_empty(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import HtmlExtractor

        doc = HtmlExtractor().extract("", "https://example.com/b")
        assert doc.title == "" and doc.word_count == 0 and doc.quality_score == 0.0


class TestRankerWeb:
    def _doc(
        self,
        url: str = "u1",
        text: str = "texto",
        title: str = "titulo",
        quality: float = 1.0,
        metadata: dict | None = None,
    ) -> WebDocument:
        return WebDocument(
            url=url,
            title=title,
            text=text,
            quality_score=quality,
            word_count=len(text.split()),
            metadata=metadata or {},
        )

    def test_ranking_score(self) -> None:
        from motor.core.web.ranker.ranker import RankingScore

        s = RankingScore(quality=1, position=2)
        assert s.total == 3.0
        d = s.to_dict()
        assert d["quality"] == 1.0 and d["total"] == 3.0

    def test_ranked_document(self) -> None:
        from motor.core.web.ranker.ranker import RankedDocument, RankingScore

        r = RankedDocument(document=self._doc(), score=RankingScore(quality=1))
        assert r.final_score == 1.0
        assert isinstance(r.score_breakdown, dict)

    def test_rank_ordering(self) -> None:
        from motor.core.web.ranker.ranker import DocumentRanker

        docs = [
            self._doc(url="b", title="python", text="python es genial" * 30),
            self._doc(url="a", title="otro", text="sin coincidencias"),
        ]
        ranker = DocumentRanker()
        ranked = ranker.rank("python", docs, positions={"b": 0, "a": 5})
        assert ranked[0].document.url == "b"
        assert "quality" in ranker.weights

    def test_rank_penalties(self) -> None:
        from motor.core.web.ranker.ranker import DocumentRanker

        short = self._doc(url="c", text="corto", title="t")
        empty = WebDocument(url="d", title="", text="", word_count=0)
        ranker = DocumentRanker()
        ranked = ranker.rank("zzz", [empty, short])
        assert ranked[-1].score.short_penalty == ranker.weights["short_penalty"]
        assert ranked[0].score.empty_penalty == ranker.weights["empty_penalty"]

    def test_rank_canonical_bonus(self) -> None:
        from motor.core.web.ranker.ranker import DocumentRanker

        doc = self._doc(url="u", metadata={"canonical_url": "https://canon/x"})
        ranker = DocumentRanker({"canonical_bonus": 2.0})
        (r,) = ranker.rank("q", [doc])
        assert r.score.canonical_bonus == 2.0

    def test_match_count(self) -> None:
        from motor.core.web.ranker.ranker import DocumentRanker

        assert DocumentRanker()._match_count("a b a", ["a"]) == 2


class TestSearcherDuckDuckGo:
    def test_parse_results(self) -> None:
        from motor.core.web.searcher.providers.duckduckgo import _parse_results

        html = """
        <a class="result__a" href="x">T1</a><a class="result__snippet" href="y">S1</a>
        <a class="result__a" href="x2">T2</a><a class="result__snippet" href="y2">S2</a>
        <a class="result__url" href="http://u1"></a><a class="result__url" href="http://u2"></a>
        """
        results = _parse_results(html)
        assert len(results) == 2
        assert results[0]["title"] == "T1"
        assert results[0]["url"] == "http://u1"
        assert _parse_results("") == []

    def test_search_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import duckduckgo as mod

        def fake_post(*a: Any, **k: Any) -> FakeResponse:
            return FakeResponse(
                content=b'<a class="result__a">T</a><a class="result__url" href="http://u"></a><a class="result__snippet">S</a>'
            )

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        provider = mod.DuckDuckGoSearchProvider()
        assert provider.name == "duckduckgo"
        results = provider.search("query", limit=5)
        assert len(results) == 1
        assert results[0].source == "duckduckgo"

    def test_search_retries_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import duckduckgo as mod

        monkeypatch.setattr(mod.time, "sleep", lambda s: None)

        def fake_post(*a: Any, **k: Any) -> FakeResponse:
            raise httpx.TimeoutException("t")

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        with pytest.raises(RuntimeError):
            mod.DuckDuckGoSearchProvider(max_retries=1).search("q")

    def test_search_retries_429_then_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import duckduckgo as mod

        monkeypatch.setattr(mod.time, "sleep", lambda s: None)
        calls = {"n": 0}

        def fake_post(*a: Any, **k: Any) -> FakeResponse:
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "u"), response=httpx.Response(429))
            return FakeResponse()

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        assert mod.DuckDuckGoSearchProvider(max_retries=1).search("q") == []

    def test_search_http_error_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import duckduckgo as mod

        def fake_post(*a: Any, **k: Any) -> FakeResponse:
            raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "u"), response=httpx.Response(500))

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        with pytest.raises(httpx.HTTPStatusError):
            mod.DuckDuckGoSearchProvider().search("q")

    def test_search_connection_error_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import duckduckgo as mod

        monkeypatch.setattr(mod.time, "sleep", lambda s: None)

        def fake_post(*a: Any, **k: Any) -> FakeResponse:
            raise httpx.ConnectError("c")

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        with pytest.raises(RuntimeError):
            mod.DuckDuckGoSearchProvider(max_retries=1).search("q")


class TestSearcherSearxng:
    def test_search_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import searxng as mod

        def fake_get(*a: Any, **k: Any) -> FakeJsonResponse:
            return FakeJsonResponse()

        monkeypatch.setattr(mod.httpx, "get", fake_get)
        p = mod.SearXNGSearchProvider(base_url="http://sx", max_retries=0)
        assert p.name == "searxng"
        results = p.search("q", limit=10)
        assert results[0].published == "2026-01-01" and results[0].source == "searxng"

    def test_search_timeout_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import searxng as mod

        monkeypatch.setattr(mod.time, "sleep", lambda s: None)

        def fake_get(*a: Any, **k: Any) -> FakeJsonResponse:
            raise httpx.TimeoutException("t")

        monkeypatch.setattr(mod.httpx, "get", fake_get)
        with pytest.raises(RuntimeError):
            mod.SearXNGSearchProvider(base_url="http://sx", max_retries=1).search("q")

    def test_search_503_then_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import searxng as mod

        monkeypatch.setattr(mod.time, "sleep", lambda s: None)
        calls = {"n": 0}

        def fake_get(*a: Any, **k: Any) -> FakeJsonResponse:
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.HTTPStatusError("x", request=httpx.Request("GET", "u"), response=httpx.Response(503))
            return FakeJsonResponse()

        monkeypatch.setattr(mod.httpx, "get", fake_get)
        assert len(mod.SearXNGSearchProvider(base_url="http://sx", max_retries=1).search("q")) == 1

    def test_search_http_500_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import searxng as mod

        def fake_get(*a: Any, **k: Any) -> FakeJsonResponse:
            raise httpx.HTTPStatusError("x", request=httpx.Request("GET", "u"), response=httpx.Response(500))

        monkeypatch.setattr(mod.httpx, "get", fake_get)
        with pytest.raises(httpx.HTTPStatusError):
            mod.SearXNGSearchProvider(base_url="http://sx").search("q")

    def test_search_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.searcher.providers import searxng as mod

        monkeypatch.setattr(mod.time, "sleep", lambda s: None)

        def fake_get(*a: Any, **k: Any) -> FakeJsonResponse:
            raise httpx.ConnectError("c")

        monkeypatch.setattr(mod.httpx, "get", fake_get)
        with pytest.raises(RuntimeError):
            mod.SearXNGSearchProvider(base_url="http://sx", max_retries=1).search("q")


class TestSummarizerWeb:
    def test_split_sentences(self) -> None:
        from motor.core.web.summarizer.summarizer import split_sentences

        assert split_sentences("Hola mundo. Esto es otra frase.") == ["Hola mundo.", "Esto es otra frase."]
        assert split_sentences("Hola.\nSegunda línea") == ["Hola.", "Segunda línea"]
        assert split_sentences("") == [""]
        short = split_sentences("A. Segunda frase larga aquí.")
        assert len(short) == 2 and short[0].startswith("A.")

    def test_scores(self) -> None:
        from motor.core.web.summarizer.summarizer import _length_score, _position_score, _tf_scores, _title_overlap

        assert _tf_scores("") == {}
        tf = _tf_scores("a a a a b")
        assert tf["a"] <= 0.3
        assert _title_overlap("python guia", "python es genial") > 0
        assert _title_overlap("", "x") == 0.0
        assert _length_score(20) == pytest.approx(1.0, abs=0.01)
        assert _position_score(0, 1) == 1.0
        assert _position_score(2, 4) < 1.0

    def test_score_sentence(self) -> None:
        from motor.core.web.summarizer.summarizer import score_sentence

        assert score_sentence("", {}, "", 0, 1) == 0.0
        s = score_sentence("python es un lenguaje", {"python": 0.2}, "python", 0, 3)
        assert s > 0

    def test_summarize_single(self) -> None:
        from motor.core.web.summarizer.summarizer import ExtractiveSummarizer

        doc = WebDocument(
            url="u1",
            title="Python",
            text="Python es un lenguaje de programación. Es muy popular en ciencia. Se usa en datos y web. Tiene una comunidad enorme.",
            word_count=20,
        )
        s = ExtractiveSummarizer().summarize([doc], max_length=2)
        assert s.sentences and s.source_documents == ["u1"]
        assert s.compression_ratio >= 0
        assert s.sentence_origins[0]["url"] == "u1"

    def test_summarize_dedup_and_empty(self) -> None:
        from motor.core.web.summarizer.summarizer import ExtractiveSummarizer

        text = "Primera frase única aquí. Segunda frase única allá."
        doc1 = WebDocument(url="u1", title="t", text=text, word_count=6)
        doc2 = WebDocument(url="u2", title="t", text=text, word_count=6)
        s = ExtractiveSummarizer().summarize([doc1, doc2], max_length=10)
        assert len(s.source_documents) == 2
        assert len(s.sentences) <= 2
        assert ExtractiveSummarizer().summarize([]).sentences == []

    def test_summarize_empty_text_doc(self) -> None:
        from motor.core.web.summarizer.summarizer import ExtractiveSummarizer

        doc = WebDocument(url="u", title="", text="", word_count=0)
        s = ExtractiveSummarizer().summarize([doc])
        assert s.text == ""


class TestCleanerWeb:
    def test_normalize_url(self) -> None:
        from motor.core.web.cleaner.url_utils import normalize_url

        assert normalize_url("HTTPS://Example.COM/Path/") == "https://example.com/Path"
        assert normalize_url("http://example.com/page#frag") == "http://example.com/page"
        assert normalize_url("http://example.com/") == "http://example.com/"
        assert normalize_url("http://example.com") == "http://example.com/"

    def test_get_document_id_and_hash(self) -> None:
        from motor.core.web.cleaner.url_utils import content_hash, get_document_id

        assert get_document_id("http://x/", "https://canon/y") == "https://canon/y"
        assert get_document_id("http://x/") == "http://x/"
        assert content_hash("a   b") == content_hash("a b")
        assert len(content_hash("x")) == 64

    def test_document_cleaner(self) -> None:
        from motor.core.web.cleaner.cleaner import DocumentCleaner

        empty = WebDocument(url="HTTP://X/", title="t", text="")
        short = WebDocument(url="http://x/", title="t", text="solo dos")
        ok = WebDocument(url="http://y/", title="t", text="tres palabras aqui")
        result = DocumentCleaner().clean([empty, short, ok])
        assert len(result.documents) == 1
        assert result.documents[0].url == "http://y/"
        assert result.stats.documents_removed_empty == 2

    def test_cleaned_stats(self) -> None:
        from motor.core.web.cleaner.cleaner import CleanedStats

        s = CleanedStats(documents_received=4, documents_removed_empty=1, documents_removed_duplicate_hash=1)
        assert s.documents_removed == 2
        assert s.duplication_pct == 50.0
        assert CleanedStats().duplication_pct == 0.0
        d = s.to_dict()
        assert d["duplication_pct"] == 50.0

    def test_deduplication(self) -> None:
        from motor.core.web.cleaner.cleaner import CleanedStats
        from motor.core.web.cleaner.deduplication import DeduplicationEngine

        base = WebDocument(url="http://x/", title="t", text="contenido identico aqui", quality_score=0.5)
        dup_url = WebDocument(url="http://x/", title="t", text="contenido identico aqui", quality_score=0.5)
        dup_hash = WebDocument(url="http://y/", title="t", text="contenido  identico  aqui", quality_score=0.9)
        stats = CleanedStats(documents_received=3)
        result = DeduplicationEngine().deduplicate([base, dup_url, dup_hash], stats=stats)
        assert len(result) == 1
        assert result[0] is dup_hash
        assert stats.documents_removed_duplicate_url == 1
        assert stats.documents_removed_duplicate_hash == 1
        assert stats.documents_unique == 1

    def test_deduplication_replaces_best(self) -> None:
        from motor.core.web.cleaner.deduplication import DeduplicationEngine

        base = WebDocument(url="http://x/", title="t", text="contenido comun", quality_score=0.2)
        better = WebDocument(url="http://x/", title="t", text="contenido comun", quality_score=0.9)
        result = DeduplicationEngine().deduplicate([base, better])
        assert result == [better]

    def test_deduplication_clean_stats_none(self) -> None:
        from motor.core.web.cleaner.deduplication import DeduplicationEngine

        result = DeduplicationEngine().deduplicate([WebDocument(url="http://x/", title="t", text="a b c")])
        assert len(result) == 1


class TestCitationWeb:
    def test_make_evidence_id(self) -> None:
        from motor.core.web.citation.citation import make_evidence_id

        a = make_evidence_id("d1", 3, "h")
        assert len(a) == 16
        assert a == make_evidence_id("d1", 3, "h")

    def test_evidence_to_dict(self) -> None:
        from motor.core.web.citation.citation import Evidence

        e = Evidence(
            evidence_id="e",
            document_url="u",
            canonical_url=None,
            title="t",
            document_index=0,
            sentence_position=1,
            fragment="f",
            content_hash="h",
            document_id="d",
            fetched_at=1.0,
            quality_score=0.8,
        )
        d = e.to_dict()
        assert d["evidence_id"] == "e" and d["quality_score"] == 0.8

    def test_bundle_to_dict(self) -> None:
        from motor.core.web.citation.citation import CitationBundle

        b = CitationBundle(summary="s", citations=[], evidence=[])
        d = b.to_dict()
        assert d["summary"] == "s" and d["evidence"] == []

    def test_engine_build(self) -> None:
        from motor.core.web.citation.citation import CitationEngine
        from motor.core.web.summarizer.summarizer import ExtractiveSummarizer

        doc = WebDocument(
            url="http://x/",
            title="Python",
            text="Python es un lenguaje de programación muy popular. Se usa en ciencia de datos.",
            word_count=15,
            metadata={"canonical_url": "https://canon/x"},
        )
        summary = ExtractiveSummarizer().summarize([doc], max_length=2)
        bundle = CitationEngine().build(summary, [doc])
        assert len(bundle.citations) == len(summary.sentences)
        assert bundle.evidence
        assert bundle.traceability_report["total_citations"] == len(bundle.citations)

    def test_engine_skips_missing_doc(self) -> None:
        from motor.core.web.citation.citation import CitationEngine
        from motor.core.web.summarizer.summarizer import ExtractiveSummarizer

        doc = WebDocument(
            url="http://x/", title="t", text="Frase principal de prueba. Otra frase de relleno.", word_count=8
        )
        summary = ExtractiveSummarizer().summarize([doc], max_length=2)
        bundle = CitationEngine().build(summary, [])
        assert bundle.citations == []
        assert _find_doc_index([], "http://x/") == -1


def _find_doc_index(documents: list[WebDocument], url: str) -> int:
    from motor.core.web.citation.citation import _find_doc_index as f

    return f(documents, url)


def _make_registry() -> Any:
    from motor.core.web.registry import Registry

    reg = Registry()
    reg.register_searcher(
        "s1", FakeSearchProvider([SearchResult(title="t", url="http://u/", snippet="s", source="s1")])
    )
    reg.register_crawler("fake-crawler", FakeCrawler())
    reg.register_extractor("fake-extractor", FakeExtractor())
    reg.register_ranker("default", FakeRanker())
    reg.register_summarizer("llm", FakeSummarizer())
    return reg


class TestWebPipeline:
    def test_search(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        p = WebPipeline(_make_registry())
        results = p.search("q")
        assert len(results) == 1
        assert p.registry is not None

    def test_search_missing_source_skipped(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        p = WebPipeline(_make_registry())
        assert p.search("q", sources=["nope"]) == []

    def test_fetch_extract_clean_rank(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        p = WebPipeline(_make_registry())
        assert p.fetch("http://u/", crawler="fake-crawler") == "<html>ok</html>"
        doc = p.extract("<html>x</html>", "http://u/", extractor="fake-extractor")
        assert doc.url == "http://u/"
        cleaned = p.clean([doc])
        assert cleaned.documents
        results = p.rank([SearchResult(title="t", url="u", snippet="s", source="x")], "q")
        assert len(results) == 1

    def test_rank_documents(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        p = WebPipeline(_make_registry())
        doc = WebDocument(url="u", title="t", text=" ".join(["palabra"] * 100), word_count=100)
        ranked = p.rank_documents("q", [doc])
        assert len(ranked) == 1 and ranked[0].final_score >= 0

    def test_summarize_documents_and_cite(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        p = WebPipeline(_make_registry())
        doc = WebDocument(
            url="http://u/", title="t", text="Frase principal de prueba aquí. Otra frase más de relleno.", word_count=10
        )
        s = p.summarize_documents([doc])
        assert s.sentences
        bundle = p.cite(s, [doc])
        assert bundle.evidence

    def test_summarize_llm(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        p = WebPipeline(_make_registry())
        summary, citations = p.summarize("q", [WebDocument(url="u", title="t", text="x")])
        assert summary == "resumen" and citations

    def test_run_no_extract_no_summarize(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        p = WebPipeline(_make_registry())
        r = p.run("q", extract=False, summarize=False)
        assert r["search_results"] and r["results"] == []
        assert "stage_times" in r

    def test_run_full(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        p = WebPipeline(_make_registry())
        r = p.run("q", limit=10, crawler="fake-crawler", extractor="fake-extractor")
        assert r["summary"] == "resumen"
        assert r["citations"]

    def test_run_fetch_error_continues(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        reg = _make_registry()
        reg.register_crawler("bad", FakeCrawler(error=RuntimeError("boom")))
        p = WebPipeline(reg)
        r = p.run("q", crawler="bad")
        assert r["results"] == []

    def test_pipeline_stage_enum(self) -> None:
        from motor.core.web.pipeline import PipelineStage

        assert PipelineStage.SEARCH.value == "search"
        assert list(PipelineStage) == [
            PipelineStage.SEARCH,
            PipelineStage.CRAWL,
            PipelineStage.EXTRACT,
            PipelineStage.CLEAN,
            PipelineStage.RANK,
            PipelineStage.SUMMARIZE,
            PipelineStage.VALIDATE,
        ]


class TestPersistWeb:
    def test_persist_empty(self) -> None:
        from motor.core.web.pipeline import WebPipeline

        assert WebPipeline(_make_registry()).persist([], store=object()) == {"stored": 0, "errors": []}

    def test_persist_fusion_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.web.pipeline import WebPipeline

        class Boom:
            @staticmethod
            def default() -> Any:
                raise RuntimeError("fusion boom")

        monkeypatch.setattr("motor.core.fusion.engine.FusionPipeline", Boom)
        result = WebPipeline(_make_registry()).persist([WebDocument(url="u", title="t", text="a b c")], store=object())
        assert result["stored"] == 0 and result["errors"]

    def test_persist_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.fusion.models import KnowledgeFact
        from motor.core.web.pipeline import WebPipeline

        fact = KnowledgeFact(id="kf1", subject="s", predicate="p", object="o", confidence=0.5)

        class FakeResult:
            accepted: list[KnowledgeFact] = [fact]  # noqa: RUF012

        class FakePipeline:
            @staticmethod
            def default() -> Any:
                return FakePipeline()

            def run(self, bundle: Any, documents: list[WebDocument]) -> FakeResult:
                return FakeResult()

        class FakeStore:
            def __init__(self) -> None:
                self.stored: list[Any] = []

            def store(self, sf: Any) -> None:
                self.stored.append(sf)

        monkeypatch.setattr("motor.core.fusion.engine.FusionPipeline", FakePipeline)
        store = FakeStore()
        result = WebPipeline(_make_registry()).persist([WebDocument(url="u", title="t", text="a b c")], store=store)
        assert result["stored"] == 1
        assert len(store.stored) == 1

    def test_persist_fact_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.fusion.models import KnowledgeFact
        from motor.core.web.pipeline import WebPipeline

        class FakeResult:
            accepted: list[KnowledgeFact] = [
                KnowledgeFact(id="bad", subject="s", predicate="p", object="o", confidence=0.5)
            ]  # noqa: RUF012

        class FakePipeline:
            @staticmethod
            def default() -> Any:
                return FakePipeline()

            def run(self, bundle: Any, documents: list[WebDocument]) -> FakeResult:
                return FakeResult()

        class FakeStore:
            def store(self, sf: Any) -> None:
                raise RuntimeError("store boom")

        monkeypatch.setattr("motor.core.fusion.engine.FusionPipeline", FakePipeline)
        result = WebPipeline(_make_registry()).persist(
            [WebDocument(url="u", title="t", text="a b c")], store=FakeStore()
        )
        assert result["stored"] == 0 and result["errors"]


class TestCoberturaFinaWeb:
    """Cobertura 100x100: remanentes finos del módulo web (TASK-20260814-001)."""

    def test_dedup_por_document_id(self) -> None:
        from motor.core.web.cleaner.deduplication import DeduplicationEngine

        a = WebDocument(
            url="http://x/1",
            title="t",
            text="mismo documento aqui",
            quality_score=0.3,
            metadata={"canonical_url": "https://canon/c"},
        )
        b = WebDocument(
            url="http://x/2",
            title="t",
            text="mismo documento aqui",
            quality_score=0.6,
            metadata={"canonical_url": "https://canon/c"},
        )
        result = DeduplicationEngine().deduplicate([a, b])
        assert result == [b]

    def test_parse_attrs(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import _parse_attrs

        assert _parse_attrs([("a", None), ("b", "x")]) == {"b": "x"}

    def test_skip_anidado(self) -> None:
        from motor.core.web.extractor.providers.html_extractor import _clean_html

        html = "<html><body><nav><div>dentro</div></nav><p>Fuera</p></body></html>"
        text = _clean_html(html)
        assert "dentro" not in text and "Fuera" in text

    def test_split_sentences_anexa_corta(self) -> None:
        from motor.core.web.summarizer.summarizer import split_sentences

        assert split_sentences("Frase larga. X") == ["Frase larga. X"]
        assert split_sentences("Hola. X") == ["Hola. X"]

    def test_is_private_url_malformed(self) -> None:
        from motor.core.web.crawler.providers.httpx_crawler import _is_private_url

        assert _is_private_url("http://[::1") is False

    def test_fetch_get_error_y_size(self, monkeypatch: pytest.MonkeyPatch) -> None:

        c = self._crawler(monkeypatch, get_raise=httpx.TimeoutException("t"))
        assert c.fetch_raw("http://public.example/x").error == "timeout"

        c2 = self._crawler(
            monkeypatch,
            head_headers={"content-type": "text/html; charset=utf-8", "content-length": "abc"},
            get_content=b"y" * 5000,
        )
        doc = c2.fetch_raw("http://public.example/x")
        assert doc.error and "exceeds" in doc.error
        assert doc.content == b"" and doc.content_length == 0

    def _crawler(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        head_headers: dict[str, str] | None = None,
        get_content: bytes = b"ok",
        get_raise: Exception | None = None,
    ):
        from motor.core.web.crawler.providers import httpx_crawler as mod

        class FakeRes:
            def __init__(self, headers: dict[str, str], content: bytes) -> None:
                self.status_code = 200
                self.headers = headers
                self.content = content
                self.url = "http://final/x"
                self.text = ""

        class FakeClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def head(self, url: str) -> FakeRes:
                return FakeRes(head_headers or {"content-type": "text/html; charset=utf-8"}, b"")

            def get(self, url: str) -> FakeRes:
                if get_raise:
                    raise get_raise
                return FakeRes({"content-type": "text/html; charset=utf-8"}, get_content)

        monkeypatch.setattr(mod.httpx, "Client", FakeClient)
        return mod.HttpCrawler(max_size=1024)
