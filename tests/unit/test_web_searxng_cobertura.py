"""Cobertura 100x100 de motor/core/web/searcher/providers/searxng.py
(TASK-20260815-003).

Cubre SearXNGSearchProvider.search con todas las ramas de reintentos,
resolución de base_url (parámetro → secret → default, con rstrip("/")),
y el mapeo de JSON a SearchResult con campos faltantes. httpx.get,
time.sleep y get_secret mockeados (sin red real).

Dependencias: httpx (instalado) — solo simulado.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import motor.core.web.searcher.providers.searxng as mod
from motor.core.web.searcher.providers.searxng import (
    DEFAULT_BASE_URL,
    SearXNGSearchProvider,
)

_JSON_OK = {
    "results": [
        {
            "title": "Titulo 1",
            "url": "https://example.com/1",
            "content": "Contenido 1",
            "publishedDate": "2026-01-01",
        },
        {"title": "Titulo 2", "url": "https://example.com/2"},
    ]
}


def _resp(status_code: int = 200, json_data: dict[str, Any] | None = None) -> SimpleNamespace:
    r = httpx.Response(
        status_code,
        request=httpx.Request("GET", "http://localhost:8888/search"),
        json=json_data or _JSON_OK,
    )
    return r


def _install_get(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[Any],
) -> list[tuple[Any, ...]]:
    """Instala un httpx.get secuencial y registra las llamadas."""
    calls: list[tuple[Any, ...]] = []

    def _fake_get(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        if not responses:
            raise AssertionError("no more responses queued")
        resp = responses.pop(0)
        if isinstance(resp, Exception) or (isinstance(resp, type) and issubclass(resp, Exception)):
            raise resp
        return resp

    monkeypatch.setattr(mod.httpx, "get", _fake_get)
    monkeypatch.setattr(mod.time, "sleep", lambda *a: None)
    return calls


class TestSearXNGSearchProvider:
    """Buscador SearXNG."""

    def test_name(self) -> None:
        assert SearXNGSearchProvider().name == "searxng"

    def test_base_url_por_parametro(self) -> None:
        p = SearXNGSearchProvider(base_url="https://search.example.com")
        assert p._base_url == "https://search.example.com"

    def test_base_url_rstrip_slash(self) -> None:
        p = SearXNGSearchProvider(base_url="https://search.example.com/")
        assert p._base_url == "https://search.example.com"

    def test_base_url_desde_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(mod, "get_secret", lambda name: "https://secret.example.com/")
        p = SearXNGSearchProvider()
        assert p._base_url == "https://secret.example.com"

    def test_base_url_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(mod, "get_secret", lambda name: None)
        p = SearXNGSearchProvider()
        assert p._base_url == DEFAULT_BASE_URL

    def test_search_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _install_get(monkeypatch, [_resp(200)])
        results = SearXNGSearchProvider().search("q")
        assert len(results) == 2
        assert results[0].title == "Titulo 1"
        assert results[0].url == "https://example.com/1"
        assert results[0].snippet == "Contenido 1"
        assert results[0].published == "2026-01-01"
        assert results[0].source == "searxng"
        assert calls[0][1]["params"] == {"q": "q", "format": "json", "count": 10}
        assert "User-Agent" in calls[0][1]["headers"]
        url_used = calls[0][0][0]
        assert url_used == f"{DEFAULT_BASE_URL}/search"

    def test_search_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _install_get(monkeypatch, [_resp(200)])
        results = SearXNGSearchProvider().search("q", limit=1)
        assert len(results) == 1
        assert calls[0][1]["params"]["count"] == 1

    def test_campos_faltantes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_get(monkeypatch, [_resp(200)])
        results = SearXNGSearchProvider().search("q")
        assert results[1].published is None
        assert results[1].snippet == ""

    def test_sin_resultados(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_get(monkeypatch, [_resp(200, json_data={"results": []})])
        assert SearXNGSearchProvider().search("q") == []

    def test_timeout_retry_y_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        timeout = httpx.TimeoutException("t")
        _install_get(monkeypatch, [timeout, _resp(200)])
        results = SearXNGSearchProvider(max_retries=2).search("q")
        assert len(results) == 2

    def test_timeout_agota(self, monkeypatch: pytest.MonkeyPatch) -> None:
        timeout = httpx.TimeoutException("t")
        _install_get(monkeypatch, [timeout, timeout, timeout])
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            SearXNGSearchProvider(max_retries=2).search("q")

    def test_rate_limited_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rate = httpx.HTTPStatusError(
            "429",
            request=httpx.Request("GET", "http://localhost:8888/search"),
            response=httpx.Response(429, request=httpx.Request("GET", "http://localhost:8888/search")),
        )
        _install_get(monkeypatch, [rate, _resp(200)])
        results = SearXNGSearchProvider(max_retries=2).search("q")
        assert len(results) == 2

    def test_rate_limited_agota(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rate = httpx.HTTPStatusError(
            "503",
            request=httpx.Request("GET", "http://localhost:8888/search"),
            response=httpx.Response(503, request=httpx.Request("GET", "http://localhost:8888/search")),
        )
        _install_get(monkeypatch, [rate, rate, rate])
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            SearXNGSearchProvider(max_retries=2).search("q")

    def test_http_status_else_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        err = httpx.HTTPStatusError(
            "500",
            request=httpx.Request("GET", "http://localhost:8888/search"),
            response=httpx.Response(500, request=httpx.Request("GET", "http://localhost:8888/search")),
        )
        _install_get(monkeypatch, [err])
        with pytest.raises(httpx.HTTPStatusError):
            SearXNGSearchProvider().search("q")

    def test_request_error_retry_y_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        err = httpx.ConnectError("boom", request=httpx.Request("GET", "http://localhost:8888/search"))
        _install_get(monkeypatch, [err, _resp(200)])
        results = SearXNGSearchProvider(max_retries=2).search("q")
        assert len(results) == 2

    def test_constructor_configurable(self) -> None:
        p = SearXNGSearchProvider(base_url="https://s/", timeout=5, user_agent="UA", max_retries=1)
        assert p._base_url == "https://s"
        assert p._timeout == 5
        assert p._user_agent == "UA"
        assert p._max_retries == 1
