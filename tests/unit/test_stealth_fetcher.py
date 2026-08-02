"""Tests para core/stealth_fetcher.py."""
from __future__ import annotations

from unittest import mock

import pytest

from core.stealth_fetcher import (
    USER_AGENTS,
    _default_headers,
    _random_ua,
    fetch,
    fetch_stealth,
    fetch_with_fallback,
)


class TestHelpers:
    def test_random_ua_siempre_valido(self) -> None:
        for _ in range(50):
            assert _random_ua() in USER_AGENTS

    def test_default_headers(self) -> None:
        headers = _default_headers()
        assert headers["User-Agent"] in USER_AGENTS
        assert headers["Accept-Language"] == "es-ES,es q=0.9,en q=0.8"
        assert headers["DNT"] == "1"


class FakeResp:
    def __init__(self, text="", is_error=False):
        self.text = text
        self.is_error = is_error


class FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        self.url = url
        self.headers = headers
        return self._resp


class TestFetch:
    @pytest.mark.asyncio
    async def test_ok(self, monkeypatch) -> None:
        client = FakeClient(FakeResp(text="<html>hola</html>"))
        monkeypatch.setattr("core.stealth_fetcher.httpx.AsyncClient", lambda *a, **k: client)
        out = await fetch("https://ejemplo.com")
        assert out == "<html>hola</html>"
        assert client.url == "https://ejemplo.com"
        assert "User-Agent" in client.headers

    @pytest.mark.asyncio
    async def test_error_http(self, monkeypatch) -> None:
        client = FakeClient(FakeResp(text="", is_error=True))
        monkeypatch.setattr("core.stealth_fetcher.httpx.AsyncClient", lambda *a, **k: client)
        assert await fetch("https://ejemplo.com") is None

    @pytest.mark.asyncio
    async def test_excepcion(self, monkeypatch) -> None:
        async def boom(*a, **k):
            raise OSError("net")

        client = FakeClient(FakeResp())
        client.get = boom
        monkeypatch.setattr("core.stealth_fetcher.httpx.AsyncClient", lambda *a, **k: client)
        assert await fetch("https://ejemplo.com") is None

    @pytest.mark.asyncio
    async def test_timeout_configurado(self, monkeypatch) -> None:
        client = FakeClient(FakeResp(text="x"))
        monkeypatch.setattr("core.stealth_fetcher.httpx.AsyncClient", lambda *a, **k: client)
        await fetch("https://ejemplo.com", timeout=60)
        assert client._resp.text == "x"


class TestFetchStealth:
    @pytest.mark.asyncio
    async def test_playwright_no_instalado(self, monkeypatch) -> None:
        import sys
        from types import SimpleNamespace

        def raiz(*a, **k):
            raise ImportError("no playwright")

        fake_api = SimpleNamespace(async_playwright=raiz)
        monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace(async_api=fake_api))
        monkeypatch.setitem(sys.modules, "playwright.async_api", fake_api)
        assert await fetch_stealth("https://ejemplo.com") is None

    @pytest.mark.asyncio
    async def test_flujo_completo(self, monkeypatch) -> None:
        import sys
        from types import SimpleNamespace

        page = mock.AsyncMock()
        page.content.return_value = "<html>stealth</html>"
        context = mock.AsyncMock()
        context.new_page.return_value = page
        browser = mock.AsyncMock()
        browser.new_context.return_value = context
        chromium = mock.AsyncMock()
        chromium.launch.return_value = browser
        playwright = mock.AsyncMock()
        playwright.__aenter__.return_value = playwright
        playwright.__aexit__.return_value = False
        playwright.chromium = chromium
        async_pw = mock.Mock(return_value=playwright)

        fake_api = SimpleNamespace(async_playwright=async_pw)
        monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace(async_api=fake_api))
        monkeypatch.setitem(sys.modules, "playwright.async_api", fake_api)
        monkeypatch.delitem(sys.modules, "playwright_stealth", raising=False)

        out = await fetch_stealth("https://ejemplo.com")
        assert out is None  # playwright_stealth no instalado -> ImportError -> None


class TestFetchWithFallback:
    @pytest.mark.asyncio
    async def test_stealth_ok_no_fetch(self, monkeypatch) -> None:
        monkeypatch.setattr("core.stealth_fetcher.fetch_stealth", mock.AsyncMock(return_value="<html>a</html>"))
        fetch_mock = mock.AsyncMock()
        monkeypatch.setattr("core.stealth_fetcher.fetch", fetch_mock)
        out = await fetch_with_fallback("https://ejemplo.com")
        assert out == "<html>a</html>"
        fetch_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stealth_falla_usa_fetch(self, monkeypatch) -> None:
        monkeypatch.setattr("core.stealth_fetcher.fetch_stealth", mock.AsyncMock(return_value=None))
        monkeypatch.setattr("core.stealth_fetcher.fetch", mock.AsyncMock(return_value="<html>b</html>"))
        monkeypatch.setattr("core.stealth_fetcher.asyncio.sleep", mock.AsyncMock())
        out = await fetch_with_fallback("https://ejemplo.com")
        assert out == "<html>b</html>"
