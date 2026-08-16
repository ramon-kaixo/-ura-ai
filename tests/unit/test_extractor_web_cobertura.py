"""Cobertura 100x100 de knowledge/engine/extractors/web.py (TASK-20260815-003).

Cubre la política SSRF (_validate_url / _validate_redirect_url con DNS
mockeado), WebExtractor.extract (URL vacía, degradación sin httpx/bs4,
SSRF y errores genéricos), _fetch_and_extract con httpx mockeado (sin red),
_parse_html con BeautifulSoup simulado, y los helpers (_is_ip_string,
_check_ip_blocked, _hash_url_stub, hashlib_content, _compute_web_quality).
"""

from __future__ import annotations

import hashlib
import socket
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from knowledge.engine.extractors import web
from knowledge.engine.extractors.base import ExtractorRegistry, get_registry
from knowledge.engine.extractors.web import (
    CloudMetadataBlocked,
    PrivateIPBlocked,
    SSRFError,
    URLSchemeBlocked,
    WebExtractor,
)

_HTML_OK = b"<html><body>contenido</body></html>"
_PUBLIC_IP = "93.184.216.34"
_PRIVATE_IP = "10.1.2.3"


class _FakeTitle:
    """Título simulado de BeautifulSoup (atributo .string)."""

    def __init__(self, string: str | None) -> None:
        self.string = string


class _FakeTag:
    """Elemento simulado con get() y acceso por clave."""

    def __init__(self, attrs: dict[str, str]) -> None:
        self._attrs = attrs

    def get(self, key: str, default: Any = "") -> Any:
        return self._attrs.get(key, default)

    def __getitem__(self, key: str) -> str:
        return self._attrs[key]


class _FakeSoup:
    """Árbol BS4 simulado configurable por escenario."""

    def __init__(
        self,
        *,
        title: str | None = None,
        meta_content: str | None = None,
        text: str = "",
        images: tuple[str, ...] = (),
        links: tuple[str, ...] = (),
    ) -> None:
        self.title = _FakeTitle(title) if title is not None else None
        self._meta = _FakeTag({"name": "description", "content": meta_content}) if meta_content is not None else None
        self._text = text
        self._images = [_FakeTag({"src": src}) for src in images]
        self._links = [_FakeTag({"href": href}) for href in links]

    def find(self, name: str, attrs: dict[str, str] | None = None) -> _FakeTag | None:
        if name == "meta" and attrs == {"name": "description"}:
            return self._meta
        return None

    def get_text(self, separator: str = "", strip: bool = False) -> str:
        return self._text

    def find_all(self, name: str, **kwargs: Any) -> list[_FakeTag]:
        if name == "img":
            return self._images
        if name == "a" and kwargs.get("href"):
            return self._links
        return []


class _FakeBeautifulSoup:
    """Constructor BS4 simulado: devuelve el escenario activo."""

    scenario: _FakeSoup = _FakeSoup()

    def __new__(cls, markup: Any, parser: str, *extra_args: Any, **extra_kwargs: Any) -> _FakeSoup:
        return cls.scenario


def _activate_soup(**kwargs: Any) -> None:
    """Activa el escenario que devolverá BeautifulSoup durante un test."""
    _FakeBeautifulSoup.scenario = _FakeSoup(**kwargs)


def _make_response(
    *,
    url: str = "https://example.com/page",
    content: bytes = _HTML_OK,
    status_code: int = 200,
    content_type: str = "text/html; charset=utf-8",
    error: Exception | None = None,
) -> SimpleNamespace:
    """Respuesta HTTP falsa con raise_for_status configurable."""

    def raise_for_status() -> None:
        if error is not None:
            raise error

    return SimpleNamespace(
        url=url,
        content=content,
        status_code=status_code,
        headers={"content-type": content_type},
        raise_for_status=raise_for_status,
    )


def _install_http(monkeypatch: pytest.MonkeyPatch, response: SimpleNamespace) -> MagicMock:
    """Sustituye httpx.Client/HTTPTransport/Timeout por dobles sin red."""
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.get.return_value = response
    monkeypatch.setattr("httpx.Client", lambda *a, **k: client)
    monkeypatch.setattr("httpx.HTTPTransport", MagicMock)
    monkeypatch.setattr("httpx.Timeout", MagicMock)
    return client


def _mock_dns(monkeypatch: pytest.MonkeyPatch, ips: list[str] | Exception) -> None:
    """Mockea socket.getaddrinfo con IPs fijas o un fallo lanzado."""

    if isinstance(ips, Exception):

        def fail(host: str, port: int | None = None) -> list[Any]:
            raise ips

        monkeypatch.setattr(web.socket, "getaddrinfo", fail)
        return

    def resolve(host: str, port: int | None = None) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in ips]

    monkeypatch.setattr(web.socket, "getaddrinfo", resolve)


def _source(url: str) -> web.AssetSource:
    return web.AssetSource(kind="web", location=url)


@pytest.fixture(autouse=True)
def _fake_bs4(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inyecta el módulo bs4 simulado (bs4 no está instalado en .venv)."""
    monkeypatch.setitem(sys.modules, "bs4", SimpleNamespace(BeautifulSoup=_FakeBeautifulSoup))


class TestIdentidadRegistro:
    def test_identidad(self) -> None:
        assert WebExtractor.id == "web"
        assert WebExtractor.version == "1.0.0"
        assert WebExtractor.supported_mime_types == ["text/html"]
        assert WebExtractor.cost == "O(n)"

    def test_registrado_en_registry(self) -> None:
        assert isinstance(get_registry(), ExtractorRegistry)
        assert isinstance(get_registry().get("web"), WebExtractor)


class TestExtract:
    def test_url_vacia(self) -> None:
        extractor = WebExtractor()
        result = extractor.extract(_source(""))

        assert result.asset is None
        assert result.errors == ["Empty URL"]
        assert result.duration_ms >= 0

    def test_degradado_sin_httpx_ni_bs4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(web, "_HAS_HTTPX", False)
        monkeypatch.setattr(web, "_HAS_BS4", False)
        url = "https://example.com/degraded"

        result = WebExtractor().extract(_source(url))

        assert result.errors == []
        assert result.asset is not None
        assert result.asset.quality == 0.3
        assert result.asset.metadata["_degraded"] is True
        assert result.asset.metadata["_degraded_reason"] == "httpx or beautifulsoup4 not installed"
        assert result.asset.metadata["url"] == url
        assert result.asset.metadata["wraps"] == f"source:{url}"
        assert result.asset.metadata["extracted_at"]
        assert result.asset.asset_id == hashlib.sha256(url.encode()).hexdigest()[:16]
        assert result.asset.metadata["content_sha256"] == hashlib.sha256(url.encode()).hexdigest()

    def test_degradado_solo_sin_bs4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(web, "_HAS_HTTPX", True)
        monkeypatch.setattr(web, "_HAS_BS4", False)

        result = WebExtractor().extract(_source("https://example.com/d2"))

        assert result.asset is not None
        assert result.asset.metadata["_degraded"] is True

    def test_esquema_no_permitido(self) -> None:
        result = WebExtractor().extract(_source("ftp://example.com/file"))

        assert result.asset is None
        assert any("Scheme 'ftp' not allowed" in error for error in result.errors)

    def test_ip_privada_rechazada(self) -> None:
        result = WebExtractor().extract(_source("http://192.168.1.10/x"))

        assert result.asset is None
        assert any("blocked network" in error for error in result.errors)

    def test_error_generico(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(url: str) -> None:
            raise RuntimeError("boom interno")

        monkeypatch.setattr(WebExtractor, "_validate_url", staticmethod(boom))

        result = WebExtractor().extract(_source("https://example.com/x"))

        assert result.asset is None
        assert result.errors == ["Extraction error: boom interno"]

    def test_exitoso(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(web, "_HAS_HTTPX", True)
        monkeypatch.setattr(web, "_HAS_BS4", True)
        _mock_dns(monkeypatch, [_PUBLIC_IP])
        response = _make_response(content=b"<html>auto</html>")
        client = _install_http(monkeypatch, response)
        _activate_soup(
            title="Mi Título",
            meta_content="Descripción de la página",
            text="auto " * 40,
            images=("https://img.example.com/1.png", ""),
            links=("https://a.example.com", "http://b.example.com", "/relativo", "javascript:void(0)"),
        )

        result = WebExtractor().extract(_source("https://example.com/page"))

        assert result.errors == []
        assert result.asset is not None
        client.get.assert_called_once_with(
            "https://example.com/page", headers={"User-Agent": "URAKnowledgeEngine/1.0"}
        )
        metadata = result.asset.metadata
        assert metadata["title"] == "Mi Título"
        assert metadata["description"] == "Descripción de la página"
        assert metadata["text_length"] == 200
        assert metadata["text_preview"] == "auto " * 40
        assert metadata["image_count"] == 1
        assert metadata["link_count"] == 2
        assert metadata["status_code"] == 200
        assert metadata["content_type"] == "text/html; charset=utf-8"
        assert metadata["url"] == "https://example.com/page"
        assert metadata["wraps"] == "source:https://example.com/page"
        assert metadata["extracted_at"]
        assert metadata["content_sha256"] == hashlib.sha256(b"<html>auto</html>").hexdigest()
        assert result.asset.asset_id == metadata["content_sha256"][:16]
        assert result.asset.asset_type == web.AssetType.API_REFERENCE
        assert result.asset.quality == pytest.approx(1.0)

    def test_redireccion_a_ip_privada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(web, "_HAS_HTTPX", True)
        monkeypatch.setattr(web, "_HAS_BS4", True)
        _mock_dns(monkeypatch, [_PUBLIC_IP])
        _install_http(monkeypatch, _make_response(url=f"http://{_PRIVATE_IP}/evil"))
        _activate_soup()

        result = WebExtractor().extract(_source("https://example.com/start"))

        assert result.asset is None
        assert any("blocked network" in error for error in result.errors)

    def test_error_http_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        monkeypatch.setattr(web, "_HAS_HTTPX", True)
        monkeypatch.setattr(web, "_HAS_BS4", True)
        _mock_dns(monkeypatch, [_PUBLIC_IP])
        error = httpx.HTTPStatusError(
            "404 Client Error",
            request=httpx.Request("GET", "https://example.com/page"),
            response=SimpleNamespace(status_code=404),
        )
        _install_http(monkeypatch, _make_response(status_code=404, error=error))

        result = WebExtractor().extract(_source("https://example.com/page"))

        assert result.asset is None
        assert any("Extraction error" in error for error in result.errors)


class TestFetchAndExtract:
    def test_cuerpo_truncado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(web, "_HAS_HTTPX", True)
        monkeypatch.setattr(web, "_HAS_BS4", True)
        big = b"x" * (web.MAX_BODY_SIZE + 10)
        _install_http(monkeypatch, _make_response(url="https://example.com/big", content=big))
        _activate_soup(text="truncado")

        extractor = WebExtractor()
        result = extractor.extract(_source("https://example.com/big"))

        truncated = big[: web.MAX_BODY_SIZE]
        assert result.errors == []
        assert result.asset is not None
        assert result.asset.metadata["size"] == web.MAX_BODY_SIZE
        assert result.asset.metadata["content_sha256"] == hashlib.sha256(truncated).hexdigest()

    def test_sin_content_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(web, "_HAS_HTTPX", True)
        monkeypatch.setattr(web, "_HAS_BS4", True)
        _install_http(monkeypatch, _make_response(content_type=""))
        _activate_soup()

        extractor = WebExtractor()
        result = extractor.extract(_source("https://example.com/plain"))

        assert result.asset is not None
        assert result.asset.metadata["content_type"] == ""


class TestParseHtml:
    def test_completo(self) -> None:
        _activate_soup(
            title="Título con espacios  ",
            meta_content="  Descripción  ",
            text="cuerpo",
            images=("https://img.example.com/x.png",),
            links=("https://a.example.com",),
        )

        metadata = WebExtractor()._parse_html(_HTML_OK, "https://final.example.com", "https://orig.example.com", "2026-08-15T10:00:00Z", 200, "text/html")

        assert metadata["url"] == "https://final.example.com"
        assert metadata["title"] == "Título con espacios"
        assert metadata["description"] == "Descripción"
        assert metadata["text_length"] == 6
        assert metadata["text_preview"] == "cuerpo"
        assert metadata["image_count"] == 1
        assert metadata["link_count"] == 1
        assert metadata["content_sha256"] == hashlib.sha256(_HTML_OK).hexdigest()
        assert metadata["size"] == len(_HTML_OK)
        assert metadata["status_code"] == 200
        assert metadata["content_type"] == "text/html"
        assert metadata["wraps"] == "source:https://orig.example.com"
        assert metadata["extracted_at"] == "2026-08-15T10:00:00Z"
        assert metadata["_extractor"] == "web"
        assert metadata["_extractor_version"] == "1.0.0"

    def test_minimo(self) -> None:
        _activate_soup()

        metadata = WebExtractor()._parse_html(b"", "https://f.example.com", "https://o.example.com", "now", 200, "")

        assert metadata["title"] == ""
        assert metadata["description"] == ""
        assert metadata["text_length"] == 0
        assert metadata["text_preview"] == ""
        assert metadata["image_count"] == 0
        assert metadata["link_count"] == 0

    def test_titulo_sin_string_y_meta_sin_content(self) -> None:
        _activate_soup(title="", meta_content="")

        metadata = WebExtractor()._parse_html(b"", "https://f.example.com", "https://o.example.com", "now", 200, "")

        assert metadata["title"] == ""
        assert metadata["description"] == ""

    def test_enlaces_filtrados_por_prefijo_http(self) -> None:
        _activate_soup(links=("https://a.example.com", "//cdn.example.com/x", "mailto:x@example.com"))

        metadata = WebExtractor()._parse_html(b"", "https://f.example.com", "https://o.example.com", "now", 200, "")

        assert metadata["link_count"] == 1


class TestValidateUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("ftp://example.com/x", URLSchemeBlocked),
            ("file:///etc/passwd", URLSchemeBlocked),
            ("https://localhost/x", PrivateIPBlocked),
            ("https://LOCALHOST/x", PrivateIPBlocked),
            ("http://127.0.0.1/x", PrivateIPBlocked),
            ("http://[::1]/x", PrivateIPBlocked),
            ("http://10.0.0.1/x", PrivateIPBlocked),
            ("http://172.16.5.5/x", PrivateIPBlocked),
            ("http://192.168.0.5/x", PrivateIPBlocked),
            ("http://169.254.169.254/latest/meta-data/", CloudMetadataBlocked),
            ("http://100.64.1.1/x", PrivateIPBlocked),
        ],
    )
    def test_urls_bloqueadas(self, url: str, expected: type[SSRFError]) -> None:
        with pytest.raises(expected):
            WebExtractor._validate_url(url)

    def test_ip_publica_ok(self) -> None:
        assert WebExtractor._validate_url(f"http://{_PUBLIC_IP}/ok") is None

    def test_dns_fallo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_dns(monkeypatch, socket.gaierror("nodename nor servname provided"))

        with pytest.raises(SSRFError, match="DNS resolution failed"):
            WebExtractor._validate_url("https://noexiste.example.com/")

    def test_dns_ip_privada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_dns(monkeypatch, [_PRIVATE_IP])

        with pytest.raises(PrivateIPBlocked, match="blocked network"):
            WebExtractor._validate_url("https://interna.example.com/")

    def test_dns_ip_publica(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_dns(monkeypatch, [_PUBLIC_IP])

        assert WebExtractor._validate_url("https://example.com/") is None

    def test_dns_varias_direcciones_una_bloqueada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_dns(monkeypatch, [_PUBLIC_IP, _PRIVATE_IP])

        with pytest.raises(PrivateIPBlocked):
            WebExtractor._validate_url("https://dual.example.com/")

    def test_dns_resultado_no_ip_se_omite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_dns(monkeypatch, ["not-an-ip"])

        assert WebExtractor._validate_url("https://raro.example.com/") is None


class TestValidateRedirectUrl:
    @pytest.mark.parametrize(
        "url",
        ["ftp://example.com/x", "chrome://settings"],
    )
    def test_esquema_no_permitido(self, url: str) -> None:
        with pytest.raises(URLSchemeBlocked, match="Redirect to blocked scheme"):
            WebExtractor._validate_redirect_url(url)

    def test_ip_literal_publica_ok(self) -> None:
        assert WebExtractor._validate_redirect_url(f"https://{_PUBLIC_IP}/x") is None

    def test_ip_literal_privada(self) -> None:
        with pytest.raises(PrivateIPBlocked):
            WebExtractor._validate_redirect_url(f"http://{_PRIVATE_IP}/x")

    def test_dns_fallo_se_omite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_dns(monkeypatch, socket.gaierror("fail"))

        assert WebExtractor._validate_redirect_url("https://noexiste.example.com/") is None

    def test_dns_ip_privada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_dns(monkeypatch, [_PRIVATE_IP])

        with pytest.raises(PrivateIPBlocked):
            WebExtractor._validate_redirect_url("https://interna.example.com/")

    def test_dns_resultado_no_ip_se_omite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_dns(monkeypatch, ["not-an-ip"])

        assert WebExtractor._validate_redirect_url("https://raro.example.com/") is None


class TestHelpers:
    def test_is_ip_string(self) -> None:
        assert web._is_ip_string("10.0.0.1") is True
        assert web._is_ip_string("2001:db8::1") is True
        assert web._is_ip_string("example.com") is False
        assert web._is_ip_string("") is False

    def test_check_ip_blocked_metadata_cloud(self) -> None:
        with pytest.raises(CloudMetadataBlocked, match="Cloud metadata"):
            web._check_ip_blocked(web.ipaddress.ip_address("169.254.169.254"), "169.254.169.254")

    def test_check_ip_blocked_privada(self) -> None:
        with pytest.raises(PrivateIPBlocked, match=f"IP {_PRIVATE_IP}"):
            web._check_ip_blocked(web.ipaddress.ip_address(_PRIVATE_IP), "interna.example.com")

    def test_check_ip_blocked_publica(self) -> None:
        assert web._check_ip_blocked(web.ipaddress.ip_address(_PUBLIC_IP), "example.com") is None

    def test_hash_url_stub(self) -> None:
        assert web._hash_url_stub("https://example.com") == hashlib.sha256(b"https://example.com").hexdigest()
        assert web._hash_url_stub("a") != web._hash_url_stub("b")

    def test_hashlib_content(self) -> None:
        assert web.hashlib_content(b"abc") == hashlib.sha256(b"abc").hexdigest()

    @pytest.mark.parametrize(
        ("metadata", "expected"),
        [
            ({}, 0.3),
            ({"status_code": 500, "text_length": 10}, 0.3),
            ({"title": "T"}, 0.45),
            ({"title": "T", "description": "D"}, 0.55),
            ({"title": "T", "description": "D", "text_length": 150}, 0.7),
            ({"title": "T", "description": "D", "text_length": 150, "image_count": 1}, 0.8),
            ({"title": "T", "description": "D", "text_length": 150, "image_count": 1, "link_count": 2}, 0.9),
            ({"title": "T", "description": "D", "text_length": 150, "image_count": 1, "link_count": 2, "status_code": 200}, 1.0),
        ],
    )
    def test_compute_web_quality(self, metadata: dict[str, Any], expected: float) -> None:
        assert web._compute_web_quality(metadata) == pytest.approx(expected)
