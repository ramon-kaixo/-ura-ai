"""Proveedor de búsqueda DuckDuckGo.

Usa el endpoint HTML público (sin API key). Sin dependencias adicionales.
"""

from __future__ import annotations

import logging
import re
import time

import httpx

from motor.core.web.base import SearchProvider
from motor.core.web.models import SearchResult

log = logging.getLogger(__name__)

SEARCH_URL = "https://html.duckduckgo.com/html"
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; URA/1.0; +https://github.com/anomalyco/ura) Web Intelligence"


def _parse_results(html: str) -> list[dict[str, str]]:
    """Parsea resultados de la página HTML de DuckDuckGo."""
    results: list[dict[str, str]] = []
    # DuckDuckGo HTML results are in <a class="result__a"> tags
    # with sibling <a class="result__snippet"> for snippets
    titles = re.findall(
        r'<a[^>]+class="result__a"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )
    urls = re.findall(
        r'<a[^>]+class="result__url"[^>]*href="([^"]+)"',
        html,
    )
    snippets = re.findall(
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )

    for i in range(max(len(titles), len(urls), len(snippets))):
        title = re.sub(r"<[^>]+>", "", titles[i]) if i < len(titles) else ""
        url = urls[i] if i < len(urls) else ""
        snippet = re.sub(r"<[^>]+>", "", snippets[i]) if i < len(snippets) else ""
        if title and url:
            results.append(
                {
                    "title": title.strip(),
                    "url": url.strip(),
                    "snippet": snippet.strip(),
                },
            )
    return results


class DuckDuckGoSearchProvider(SearchProvider):
    """Buscador DuckDuckGo vía endpoint HTML público."""

    def __init__(
        self,
        timeout: int = 10,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = 2,
    ) -> None:
        self._timeout = timeout
        self._user_agent = user_agent
        self._max_retries = max_retries

    @property
    def name(self) -> str:
        return "duckduckgo"

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return self._search_once(query, limit)
            except httpx.TimeoutException as e:
                last_error = e
                log.warning("ddg timeout (attempt %d/%d): %s", attempt + 1, self._max_retries + 1, query)
                time.sleep(1.0 * (attempt + 1))
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503):
                    last_error = e
                    log.warning("ddg rate limited (attempt %d/%d)", attempt + 1, self._max_retries + 1)
                    time.sleep(2.0 * (attempt + 1))
                else:
                    raise
            except httpx.RequestError as e:
                last_error = e
                log.warning("ddg connection error (attempt %d/%d): %s", attempt + 1, self._max_retries + 1, e)
                time.sleep(1.0 * (attempt + 1))

        msg = f"DuckDuckGo search failed after {self._max_retries + 1} attempts"
        raise RuntimeError(msg) from last_error

    def _search_once(self, query: str, limit: int = 10) -> list[SearchResult]:
        r = httpx.post(
            SEARCH_URL,
            data={"q": query},
            headers={"User-Agent": self._user_agent},
            timeout=self._timeout,
            follow_redirects=True,
        )
        r.raise_for_status()
        raw = _parse_results(r.text)

        return [
            SearchResult(
                title=item["title"],
                url=item["url"],
                snippet=item["snippet"],
                source=self.name,
            )
            for item in raw[:limit]
        ]
