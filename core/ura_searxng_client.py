#!/usr/bin/env python3
"""
URA SearXNG Client — N2 Infrastructure (Fase 2, opcional)

Cliente async para una instancia local de SearXNG (http://localhost:8080).
SearXNG es un metabuscador gratuito de código abierto.

En Fase 1 usamos DuckDuckGo directo. Este módulo se activa cuando el usuario
quiera privacidad adicional o reducir dependencia de DDG, instalando SearXNG
localmente (con o sin Docker).

Contrato compatible con `DDGClient.search()` para que el swarm pueda
intercambiarlos sin cambios estructurales.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

try:
    import aiohttp  # type: ignore

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None  # type: ignore

logger = logging.getLogger("ura_searxng_client")

DEFAULT_BASE = "http://localhost:8080"
DEFAULT_TIMEOUT = 20
DEFAULT_MAX_RESULTS = 10
MIN_JITTER = 0.3
MAX_JITTER = 1.5
MAX_RETRIES = 3


class SearXNGClient:
    """Async client for a local SearXNG instance (JSON output)."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        language: str = "es",
        safesearch: int = 1,
    ) -> None:
        if not HAS_AIOHTTP:
            logger.warning("aiohttp ausente — SearXNGClient deshabilitado")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.language = language
        self.safesearch = safesearch

    async def is_alive(self) -> bool:
        """Quick HEAD/GET to verify the local instance responds."""
        if not HAS_AIOHTTP:
            return False
        timeout = aiohttp.ClientTimeout(total=5)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/healthz") as resp:
                    return resp.status < 500
        except Exception:  # noqa: BLE001
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(self.base_url) as resp:
                        return resp.status < 500
            except Exception:  # noqa: BLE001
                return False

    async def search(
        self,
        query: str,
        *,
        max_results: int = DEFAULT_MAX_RESULTS,
        categories: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run a search via SearXNG JSON API. Returns normalized results."""
        if not HAS_AIOHTTP:
            return []

        params = {
            "q": query,
            "format": "json",
            "language": self.language,
            "safesearch": self.safesearch,
        }
        if categories:
            params["categories"] = ",".join(categories)

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        for attempt in range(1, self.max_retries + 1):
            await asyncio.sleep(random.uniform(MIN_JITTER, MAX_JITTER))
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f"{self.base_url}/search", params=params) as resp:
                        if resp.status == 429:
                            logger.warning("SearXNG 429, backoff (intento %d)", attempt)
                            await asyncio.sleep(2**attempt)
                            continue
                        if resp.status >= 400:
                            logger.warning("SearXNG status %d para %r", resp.status, query)
                            return []
                        data = await resp.json()
                        results = data.get("results", [])[:max_results]
                        return [self._normalize(r) for r in results if isinstance(r, dict)]
            except TimeoutError:
                logger.warning("SearXNG timeout (intento %d/%d)", attempt, self.max_retries)
            except Exception as e:  # noqa: BLE001
                logger.warning("SearXNG error (intento %d/%d): %s", attempt, self.max_retries, e)
            await asyncio.sleep(2**attempt)

        logger.error("SearXNG: agotados reintentos para %r", query)
        return []

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": (raw.get("title") or "").strip(),
            "url": (raw.get("url") or "").strip(),
            "snippet": (raw.get("content") or "").strip(),
            "fuente_tipo": "searxng",
            "fecha": raw.get("publishedDate"),
            "source": raw.get("engine"),
        }


# Module-level singleton
_client: SearXNGClient | None = None


def get_searxng_client() -> SearXNGClient:
    global _client
    if _client is None:
        _client = SearXNGClient()
    return _client
