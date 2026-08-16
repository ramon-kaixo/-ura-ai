"""Cobertura 100x100 de motor/core/web/crawler/providers/httpx_crawler.py
(TASK-20260815-003).

Cubre HttpCrawler.fetch/fetch_raw con httpx.Client simulado (sin red real):
éxito, Content-Type no permitido, Content-Length excesivo, respuesta
excesiva, timeouts, redirecciones, RequestError, ValueError, error
genérico; SSRF (_is_private_url con socket.getaddrinfo mockeado, DNS sin
resolver, URLs malformadas), _validate_url (esquema no permitido), y
_extract_charset.

Dependencias: httpx (instalado) — solo simulado, sin llamadas de red.
"""

from __future__ import annotations

import socket
from typing import Any

import httpx
import pytest

import motor.core.web.crawler.providers.httpx_crawler as mod
from motor.core.web.crawler.providers.httpx_crawler import (
    DEFAULT_USER_AGENT,
    CrawledDocument,
    HttpCrawler,
    _extract_charset,
    _is_private_url,
    _validate_url,
)


class _FakeResponse:
    """Respuesta httpx simulada (head/get)."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        content: bytes = b"<html>ok</html>",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = httpx.URL("https://example.com/page")
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}


def _default_response() -> _FakeResponse:
    return _FakeResponse()


class _FakeClient:
    """Client httpx simulado con respuestas configurables."""

    raise_class: type[Exception] | None = None
    head_resp = _default_response
    get_resp = _default_response

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if self.raise_class is not None:
            raise self.raise_class(f"raised {self.raise_class.__name__}")
        self._head = self.head_resp()
        self._get = self.get_resp()

    def head(self, url: str) -> _FakeResponse:
        return self._head

    def get(self, url: str) -> _FakeResponse:
        return self._get


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    head: _FakeResponse | None = None,
    get: _FakeResponse | None = None,
    raise_class: type[Exception] | None = None,
) -> None:
    def _head(*args: Any, **kwargs: Any) -> _FakeResponse:
        return head or _FakeResponse()

    def _get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return get or _FakeResponse()

    _FakeClient.head_resp = _head
    _FakeClient.get_resp = _get
    _FakeClient.raise_class = raise_class
    monkeypatch.setattr(mod.httpx, "Client", _FakeClient)


class TestIsPrivateUrl:
    """Protección SSRF por IP privada."""

    def test_ip_loopback(self) -> None:
        assert _is_private_url("http://127.0.0.1/x")

    def test_ip_privada_10(self) -> None:
        assert _is_private_url("http://10.1.2.3/x")

    def test_ip_privada_172_16(self) -> None:
        assert _is_private_url("http://172.16.5.4/x")

    def test_ip_privada_192_168(self) -> None:
        assert _is_private_url("http://192.168.1.1/x")

    def test_link_local(self) -> None:
        assert _is_private_url("http://169.254.10.10/x")

    def test_ipv6_loopback(self) -> None:
        assert _is_private_url("http://[::1]/x")

    def test_ip_publica(self) -> None:
        assert not _is_private_url("http://93.184.216.34/x")

    def test_hostname_publico(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 0))])
        assert not _is_private_url("http://example.com/x")

    def test_hostname_privado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("10.0.0.5", 0))])
        assert _is_private_url("http://example.com/x")

    def test_sin_resolucion_dns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _no_dns(*a: Any, **k: Any) -> list[Any]:
            raise socket.gaierror("no dns")

        monkeypatch.setattr(socket, "getaddrinfo", _no_dns)
        assert not _is_private_url("http://notfound.invalid/x")

    def test_sin_hostname(self) -> None:
        assert _is_private_url("http:///solo-path")

    def test_url_malformada(self) -> None:
        assert not _is_private_url("http://[")


class TestValidateUrl:
    """Validación de URL para crawling."""

    def test_http_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 0))])
        _validate_url("http://example.com/x")  # no raise

    def test_https_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 0))])
        _validate_url("https://example.com/x")  # no raise

    def test_esquema_no_permitido(self) -> None:
        with pytest.raises(ValueError, match="Scheme"):
            _validate_url("ftp://example.com/x")

    def test_privada_raise(self) -> None:
        with pytest.raises(ValueError, match="private network"):
            _validate_url("http://192.168.1.1/x")


class TestExtractCharset:
    """Extracción de charset desde Content-Type."""

    def test_con_charset(self) -> None:
        assert _extract_charset("text/html; charset=utf-8") == "utf-8"

    def test_sin_charset(self) -> None:
        assert _extract_charset("text/html") == ""

    def test_charset_vacio(self) -> None:
        assert _extract_charset("charset=") == ""

    def test_case_insensitive(self) -> None:
        assert _extract_charset("TEXT/HTML; CHARSET=UTF-8") == "utf-8"

    def test_primer_charset_gana(self) -> None:
        assert _extract_charset("a; charset=latin-1; charset=utf-8") == "latin-1"


class TestHttpCrawlerFetchRaw:
    """fetch_raw: flujo principal y errores."""

    def test_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(monkeypatch)
        c = HttpCrawler()
        doc = c.fetch_raw("https://example.com/page")
        assert doc.error is None
        assert doc.status_code == 200
        assert doc.content == b"<html>ok</html>"
        assert doc.content_type == "text/html"
        assert doc.charset == "utf-8"
        assert doc.final_url == "https://example.com/page"
        assert doc.content_length == len(b"<html>ok</html>")
        assert doc.elapsed_ms >= 0

    def test_privada_sin_allow_private_raise(self) -> None:
        c = HttpCrawler()
        with pytest.raises(ValueError):
            c.fetch_raw("http://192.168.1.1/x")

    def test_privada_con_allow_private_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(monkeypatch)
        c = HttpCrawler(allow_private=True)
        doc = c.fetch_raw("http://192.168.1.1/x")
        assert doc.error is None

    def test_content_type_no_permitido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(
            monkeypatch,
            head=_FakeResponse(headers={"content-type": "application/pdf"}),
        )
        c = HttpCrawler(allowed_content_types=["text/html"])
        doc = c.fetch_raw("https://example.com/page")
        assert doc.error is not None
        assert "not in allowed list" in doc.error

    def test_content_length_excede_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(monkeypatch, head=_FakeResponse(headers={"content-length": "5000"}))
        c = HttpCrawler(max_size=100)
        doc = c.fetch_raw("https://example.com/page")
        assert doc.error is not None
        assert "exceeds max_size" in doc.error

    def test_content_length_invalido_se_ignora(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(monkeypatch, head=_FakeResponse(headers={"content-length": "abc"}))
        doc = HttpCrawler().fetch_raw("https://example.com/page")
        assert doc.error is None

    def test_respuesta_excede_max_get(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(monkeypatch, get=_FakeResponse(content=b"x" * 500))
        c = HttpCrawler(max_size=100)
        doc = c.fetch_raw("https://example.com/page")
        assert doc.error is not None
        assert "exceeds max_size" in doc.error
        assert doc.content == b""
        assert doc.content_length == 0

    def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(monkeypatch, raise_class=httpx.TimeoutException)
        doc = HttpCrawler().fetch_raw("https://example.com/page")
        assert doc.error == "timeout"

    def test_too_many_redirects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(monkeypatch, raise_class=httpx.TooManyRedirects)
        doc = HttpCrawler().fetch_raw("https://example.com/page")
        assert doc.error == "too_many_redirects"

    def test_request_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*a: Any, **k: Any) -> None:
            raise httpx.ConnectError("boom", request=httpx.Request("GET", "https://example.com"))

        monkeypatch.setattr(mod.httpx, "Client", _boom)
        doc = HttpCrawler().fetch_raw("https://example.com/page")
        assert doc.error is not None
        assert "request_error" in doc.error

    def test_request_error_real(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*a: Any, **k: Any) -> None:
            raise httpx.RequestError("boom", request=httpx.Request("GET", "https://example.com"))

        monkeypatch.setattr(mod.httpx, "Client", _boom)
        doc = HttpCrawler().fetch_raw("https://example.com/page")
        assert doc.error is not None
        assert "request_error" in doc.error

    def test_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*a: Any, **k: Any) -> None:
            raise ValueError("bad url")

        monkeypatch.setattr(mod.httpx, "Client", _boom)
        doc = HttpCrawler().fetch_raw("https://example.com/page")
        assert doc.error == "bad url"

    def test_error_generico(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*a: Any, **k: Any) -> None:
            raise RuntimeError("weird")

        monkeypatch.setattr(mod.httpx, "Client", _boom)
        doc = HttpCrawler().fetch_raw("https://example.com/page")
        assert doc.error is not None
        assert "unexpected" in doc.error


class TestHttpCrawlerFetch:
    """fetch: decodificación y errores."""

    def test_fetch_ok_texto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(
            monkeypatch,
            get=_FakeResponse(content=b"<p>hola</p>"),
        )
        text = HttpCrawler().fetch("https://example.com/page")
        assert text == "<p>hola</p>"

    def test_fetch_con_headers_content_type_sin_charset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(
            monkeypatch,
            get=_FakeResponse(content="café".encode("latin-1"), headers={"content-type": "text/html"}),
        )
        text = HttpCrawler().fetch("https://example.com/page")
        # sin charset en header → utf-8 con errors=replace
        assert "café".encode("latin-1").decode("utf-8", errors="replace") == text

    def test_fetch_raise_si_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_client(monkeypatch, head=_FakeResponse(headers={"content-type": "application/pdf"}))
        c = HttpCrawler(allowed_content_types=["text/html"])
        with pytest.raises(RuntimeError, match="Crawler error"):
            c.fetch("https://example.com/page")

    def test_fetch_decodificacion_falla_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _BrokenBytes:
            """bytes falsos cuyo decode falla en utf-8 para forzar el fallback."""

            def __init__(self) -> None:
                self._tried = False

            def __len__(self) -> int:
                return 0

            def decode(self, encoding: str = "utf-8", errors: str = "replace") -> str:
                if encoding == "utf-8" and not self._tried:
                    self._tried = True
                    raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")
                return "fallback"

        _install_fake_client(monkeypatch, get=_FakeResponse(content=_BrokenBytes()))
        text = HttpCrawler().fetch("https://example.com/page")
        assert text == "fallback"


class TestHttpCrawlerName:
    """Propiedades de identidad del crawler."""

    def test_name(self) -> None:
        assert HttpCrawler().name == "httpx"

    def test_defaults(self) -> None:
        c = HttpCrawler()
        assert c._allow_private is False
        assert c._allowed_content_types is None
        assert c._user_agent == DEFAULT_USER_AGENT

    def test_constructor_configurable(self) -> None:
        c = HttpCrawler(timeout=5, max_size=50, max_redirects=2, user_agent="UA", allowed_content_types=["text/html"])
        assert c._timeout == 5
        assert c._max_size == 50
        assert c._max_redirects == 2
        assert c._user_agent == "UA"
        assert c._allowed_content_types == ["text/html"]


class TestCrawledDocument:
    """Documento bruto."""

    def test_to_dict(self) -> None:
        doc = CrawledDocument(
            url="https://example.com/a",
            final_url="https://example.com/final",
            status_code=200,
            content_type="text/html",
            charset="utf-8",
            content=b"xxxx",
            content_length=4,
            elapsed_ms=12.34,
            error=None,
        )
        d = doc.to_dict()
        assert d["url"] == "https://example.com/a"
        assert d["final_url"] == "https://example.com/final"
        assert d["status_code"] == 200
        assert d["content_type"] == "text/html"
        assert d["charset"] == "utf-8"
        assert d["content_length"] == 4
        assert d["elapsed_ms"] == 12.3
        assert d["error"] is None

    def test_to_dict_defaults(self) -> None:
        d = CrawledDocument(url="u").to_dict()
        assert d["final_url"] == ""
        assert d["status_code"] == 0
        assert d["elapsed_ms"] == 0.0

    def test_fields_defaults(self) -> None:
        doc = CrawledDocument(url="u")
        assert doc.content == b""
        assert doc.headers == {}
        assert doc.fetch_time > 0
