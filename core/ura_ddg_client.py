#!/usr/bin/env python3
"""
URA DuckDuckGo Client — N2 Infrastructure (Fase 1)

Async wrapper for DuckDuckGo search. Substitutes SearXNG in the initial phase
(avoids Docker dependency). Supports jitter, retries, and safe timeouts.

Dependency: duckduckgo-search (DDGS class is synchronous; we wrap in executor).
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

try:
    from duckduckgo_search import DDGS  # type: ignore

    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    DDGS = None  # type: ignore

logger = logging.getLogger("ura_ddg_client")

DEFAULT_TIMEOUT = 20
DEFAULT_MAX_RESULTS = 10
MIN_JITTER_SEC = 0.5
MAX_JITTER_SEC = 2.5
MAX_RETRIES = 3


class DDGClient:
    """Async client wrapping duckduckgo-search with retries + jitter."""

    def __init__(
        self,
        *,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        region: str = "es-es",
        safesearch: str = "moderate",
    ) -> None:
        if not HAS_DDGS:
            logger.warning("duckduckgo_search no instalado — DDGClient deshabilitado")
        self.timeout = timeout
        self.max_retries = max_retries
        self.region = region
        self.safesearch = safesearch

    async def _jitter(self) -> None:
        await asyncio.sleep(random.uniform(MIN_JITTER_SEC, MAX_JITTER_SEC))

    def _sync_text_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Blocking search call executed in a thread via run_in_executor."""
        if not HAS_DDGS:
            return []
        # DDGS opens a session internally
        with DDGS(timeout=self.timeout) as ddgs:
            try:
                return list(
                    ddgs.text(
                        query,
                        region=self.region,
                        safesearch=self.safesearch,
                        max_results=max_results,
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("DDG text search falló: %s", e)
                return []

    def _sync_news_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        if not HAS_DDGS:
            return []
        with DDGS(timeout=self.timeout) as ddgs:
            try:
                return list(
                    ddgs.news(
                        query,
                        region=self.region,
                        safesearch=self.safesearch,
                        max_results=max_results,
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("DDG news search falló: %s", e)
                return []

    async def search(
        self,
        query: str,
        *,
        max_results: int = DEFAULT_MAX_RESULTS,
        mode: str = "text",
    ) -> list[dict[str, Any]]:
        """
        Run a search with up to `max_retries` attempts and exponential backoff.

        mode: "text" | "news"
        Returns a list of result dicts in a normalized shape:
            {title, url, snippet, fuente_tipo, fecha}
        """
        if not HAS_DDGS:
            return []

        loop = asyncio.get_running_loop()
        func = self._sync_news_search if mode == "news" else self._sync_text_search

        for attempt in range(1, self.max_retries + 1):
            await self._jitter()
            try:
                raw = await asyncio.wait_for(
                    loop.run_in_executor(None, func, query, max_results),
                    timeout=self.timeout + 5,
                )
                return [self._normalize(r, mode) for r in raw if isinstance(r, dict)]
            except TimeoutError:
                logger.warning("DDG search timeout (intento %d/%d)", attempt, self.max_retries)
            except Exception as e:  # noqa: BLE001
                logger.warning("DDG search error (intento %d/%d): %s", attempt, self.max_retries, e)

            # Exponential backoff: 2s, 4s, 8s...
            await asyncio.sleep(2**attempt)

        logger.error("DDG search agotó reintentos para query=%r", query)
        return []

    @staticmethod
    def _normalize(raw: dict[str, Any], mode: str) -> dict[str, Any]:
        """Normalize DDG raw result into a stable URA schema."""
        if mode == "news":
            return {
                "title": raw.get("title", "").strip(),
                "url": raw.get("url", "").strip(),
                "snippet": (raw.get("body") or raw.get("excerpt") or "").strip(),
                "fuente_tipo": "news",
                "fecha": raw.get("date"),
                "source": raw.get("source"),
            }
        # text
        return {
            "title": raw.get("title", "").strip(),
            "url": (raw.get("href") or raw.get("url") or "").strip(),
            "snippet": (raw.get("body") or "").strip(),
            "fuente_tipo": "web",
            "fecha": None,
            "source": None,
        }


# Module-level singleton
_client: DDGClient | None = None


def get_ddg_client() -> DDGClient:
    global _client
    if _client is None:
        _client = DDGClient()
    return _client
