"""Proveedor de búsqueda SearXNG.

Requiere una instancia SearXNG configurada vía WebConfig o variable de entorno.
"""

from __future__ import annotations

import logging
import time

import httpx

from motor.core.secrets import get_secret
from motor.core.web.base import SearchProvider
from motor.core.web.models import SearchResult

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8888"
DEFAULT_USER_AGENT = "URA/1.0 Web Intelligence"


class SearXNGSearchProvider(SearchProvider):
    """Buscador SearXNG vía API JSON."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 10,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = 2,
    ) -> None:
        self._base_url = (base_url or get_secret("SEARXNG_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._user_agent = user_agent
        self._max_retries = max_retries

    @property
    def name(self) -> str:
        return "searxng"

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return self._search_once(query, limit)
            except httpx.TimeoutException as e:
                last_error = e
                log.warning("searxng timeout (attempt %d/%d): %s", attempt + 1, self._max_retries + 1, query)
                time.sleep(1.0 * (attempt + 1))
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503):
                    last_error = e
                    log.warning("searxng rate limited (attempt %d/%d)", attempt + 1, self._max_retries + 1)
                    time.sleep(2.0 * (attempt + 1))
                else:
                    raise
            except httpx.RequestError as e:
                last_error = e
                log.warning("searxng connection error (attempt %d/%d): %s", attempt + 1, self._max_retries + 1, e)
                time.sleep(1.0 * (attempt + 1))

        msg = f"SearXNG search failed after {self._max_retries + 1} attempts"
        raise RuntimeError(msg) from last_error

    def _search_once(self, query: str, limit: int = 10) -> list[SearchResult]:
        r = httpx.get(
            f"{self._base_url}/search",
            params={"q": query, "format": "json", "count": limit},
            headers={"User-Agent": self._user_agent},
            timeout=self._timeout,
        )
        r.raise_for_status()
        data = r.json()

        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source=self.name,
                published=item.get("publishedDate"),
            )
            for item in data.get("results", [])[:limit]
        ]
