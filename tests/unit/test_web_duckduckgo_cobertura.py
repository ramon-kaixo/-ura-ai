"""Cobertura 100x100 de motor/core/web/searcher/providers/duckduckgo.py
(TASK-20260815-003).

Cubre DuckDuckGoSearchProvider.search con todas las ramas de reintentos
(timeout → retry → éxito, agotamiento, 429/503, otros status, RequestError),
_parse_results con campos faltantes y tags anidados, y el límite de
resultados. httpx.post y time.sleep mockeados (sin red real).

Dependencias: httpx (instalado) — solo simulado.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import motor.core.web.searcher.providers.duckduckgo as mod
from motor.core.web.searcher.providers.duckduckgo import (
    DuckDuckGoSearchProvider,
    _parse_results,
)

_HTML_OK = (
    '<a class="result__a" href="https://example.com/1">Título Uno</a>'
    '<a class="result__url" href="https://example.com/1">example.com/1</a>'
    '<a class="result__snippet">Snippet <b>uno</b>.</a>'
    '<a class="result__a" href="https://example.com/2">Título Dos</a>'
    '<a class="result__url" href="https://example.com/2">example.com/2</a>'
    '<a class="result__snippet">Snippet dos.</a>'
)


def _resp(status_code: int = 200, text: str = _HTML_OK, *, raise_for_status: bool = True) -> SimpleNamespace:
    def _raise() -> None:
        if raise_for_status:
            r = httpx.Response(status_code, request=httpx.Request("POST", mod.SEARCH_URL))
            r.raise_for_status()

    return SimpleNamespace(status_code=status_code, text=text, raise_for_status=_raise)


def _install_post(monkeypatch: pytest.MonkeyPatch, responses: list[Any]) -> list[Any]:
    """Instala un httpx.post secuencial y registra las llamadas."""
    calls: list[tuple[Any, ...]] = []

    def _fake_post(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        if not responses:
            raise AssertionError("no more responses queued")
        resp = responses.pop(0)
        if isinstance(resp, Exception) or (isinstance(resp, type) and issubclass(resp, Exception)):
            raise resp
        return resp

    monkeypatch.setattr(mod.httpx, "post", _fake_post)
    monkeypatch.setattr(mod.time, "sleep", lambda *a: None)
    return calls


class TestParseResults:
    """Parsing de HTML de resultados."""

    def test_parse_completo(self) -> None:
        results = _parse_results(_HTML_OK)
        assert len(results) == 2
        assert results[0]["title"] == "Título Uno"
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["snippet"] == "Snippet uno."
        assert results[1]["title"] == "Título Dos"

    def test_strips_tags_del_snippet(self) -> None:
        results = _parse_results(_HTML_OK)
        assert "<b>" not in results[0]["snippet"]
        assert "uno" in results[0]["snippet"]

    def test_solo_titulo_sin_url_se_omite(self) -> None:
        html = '<a class="result__a">Titulo huérfano</a>'
        assert _parse_results(html) == []

    def test_campos_faltantes_usar_vacios(self) -> None:
        html = (
            '<a class="result__a" href="https://example.com/1">Título</a>'
            '<a class="result__url" href="https://example.com/1">example.com/1</a>'
        )
        results = _parse_results(html)
        assert results == [{"title": "Título", "url": "https://example.com/1", "snippet": ""}]

    def test_sin_resultados(self) -> None:
        assert _parse_results("<html></html>") == []


class TestDuckDuckGoSearchProvider:
    """Buscador DuckDuckGo."""

    def test_name(self) -> None:
        assert DuckDuckGoSearchProvider().name == "duckduckgo"

    def test_search_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = _resp(200, _HTML_OK)
        calls = _install_post(monkeypatch, [resp])
        results = DuckDuckGoSearchProvider().search("test query")
        assert len(results) == 2
        assert results[0].title == "Título Uno"
        assert results[0].source == "duckduckgo"
        assert results[0].snippet == "Snippet uno."
        assert calls[0][1]["data"] == {"q": "test query"}
        assert "User-Agent" in calls[0][1]["headers"]

    def test_search_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = _resp(200, _HTML_OK)
        _install_post(monkeypatch, [resp])
        results = DuckDuckGoSearchProvider().search("q", limit=1)
        assert len(results) == 1

    def test_search_limit_cero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = _resp(200, _HTML_OK)
        _install_post(monkeypatch, [resp])
        assert DuckDuckGoSearchProvider().search("q", limit=0) == []

    def test_timeout_retry_y_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        timeout = httpx.TimeoutException("t")
        resp = _resp(200, _HTML_OK)
        _install_post(monkeypatch, [timeout, resp])
        provider = DuckDuckGoSearchProvider(max_retries=2)
        results = provider.search("q")
        assert len(results) == 2

    def test_timeout_agota_reintentos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        timeout = httpx.TimeoutException("t")
        _install_post(monkeypatch, [timeout, timeout, timeout])
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            DuckDuckGoSearchProvider(max_retries=2).search("q")

    def test_rate_limited_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rate = httpx.HTTPStatusError(
            "429",
            request=httpx.Request("POST", mod.SEARCH_URL),
            response=httpx.Response(429, request=httpx.Request("POST", mod.SEARCH_URL)),
        )
        resp = _resp(200, _HTML_OK)
        _install_post(monkeypatch, [rate, resp])
        results = DuckDuckGoSearchProvider(max_retries=2).search("q")
        assert len(results) == 2

    def test_rate_limited_agota(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rate = httpx.HTTPStatusError(
            "503",
            request=httpx.Request("POST", mod.SEARCH_URL),
            response=httpx.Response(503, request=httpx.Request("POST", mod.SEARCH_URL)),
        )
        _install_post(monkeypatch, [rate, rate, rate])
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            DuckDuckGoSearchProvider(max_retries=2).search("q")

    def test_http_status_else_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        err = httpx.HTTPStatusError(
            "500",
            request=httpx.Request("POST", mod.SEARCH_URL),
            response=httpx.Response(500, request=httpx.Request("POST", mod.SEARCH_URL)),
        )
        _install_post(monkeypatch, [err])
        with pytest.raises(httpx.HTTPStatusError):
            DuckDuckGoSearchProvider().search("q")

    def test_request_error_retry_y_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        err = httpx.ConnectError("boom", request=httpx.Request("POST", mod.SEARCH_URL))
        resp = _resp(200, _HTML_OK)
        _install_post(monkeypatch, [err, resp])
        results = DuckDuckGoSearchProvider(max_retries=2).search("q")
        assert len(results) == 2

    def test_sin_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        timeout = httpx.TimeoutException("t")
        _install_post(monkeypatch, [timeout])
        with pytest.raises(RuntimeError, match="failed after 1 attempts"):
            DuckDuckGoSearchProvider(max_retries=0).search("q")

    def test_constructor_configurable(self) -> None:
        provider = DuckDuckGoSearchProvider(timeout=5, user_agent="UA", max_retries=0)
        assert provider._timeout == 5
        assert provider._user_agent == "UA"
        assert provider._max_retries == 0
