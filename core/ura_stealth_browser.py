#!/usr/bin/env python3
"""
URA Stealth Browser — N2 Infrastructure (Fase 1)

Async Playwright wrapper with:
- User-Agent rotation (desktop + mobile)
- Random Accept-Language
- Jitter between navigations
- Exponential backoff on 429/403
- Automatic browser close on context exit

Use as::

    async with StealthBrowser() as browser:
        html = await browser.fetch("https://example.com")
"""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

logger = logging.getLogger("ura_stealth_browser")

try:
    from playwright.async_api import async_playwright  # type: ignore

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    async_playwright = None  # type: ignore

# Common desktop User-Agents (2024/2025)
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/123.0",
]

_ACCEPT_LANGUAGES = [
    "es-ES,es;q=0.9,en;q=0.7",
    "es-ES,es;q=0.9,ca;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,es;q=0.7",
]

DEFAULT_TIMEOUT_MS = 20_000
MIN_JITTER = 2.0
MAX_JITTER = 7.5
BACKOFF_SERIES = (60, 120, 240)  # seconds on 429/403 responses


def random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


def random_accept_language() -> str:
    return random.choice(_ACCEPT_LANGUAGES)


class StealthBrowser:
    """Async context-managed stealth browser wrapper."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        viewport: dict[str, int] | None = None,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.viewport = viewport or {"width": 1366, "height": 768}
        self._playwright = None
        self._browser = None

    async def __aenter__(self) -> StealthBrowser:
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("Playwright no está instalado")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @asynccontextmanager
    async def _new_context(self) -> AsyncIterator[Any]:
        """Create a fresh isolated context with rotated fingerprint."""
        if not self._browser:
            raise RuntimeError("StealthBrowser no inicializado — usa 'async with'")
        ctx = await self._browser.new_context(
            user_agent=random_user_agent(),
            viewport=self.viewport,
            locale="es-ES",
            extra_http_headers={"Accept-Language": random_accept_language()},
        )
        try:
            yield ctx
        finally:
            await ctx.close()

    async def fetch(self, url: str, *, wait_for_load: bool = True) -> str | None:
        """Navigate to `url` with rotation + jitter. Returns HTML string or None."""
        if not HAS_PLAYWRIGHT:
            logger.error("Playwright no está instalado — fetch abortado")
            return None

        await asyncio.sleep(random.uniform(MIN_JITTER, MAX_JITTER))

        for attempt, backoff in enumerate([0] + list(BACKOFF_SERIES)):
            if backoff:
                logger.info("Stealth backoff %ds antes de reintentar %s", backoff, url)
                await asyncio.sleep(backoff)
            try:
                async with self._new_context() as ctx:
                    page = await ctx.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    response = await page.goto(url, wait_until="domcontentloaded")
                    if response is None:
                        logger.warning("Respuesta nula en %s", url)
                        continue
                    status = response.status
                    if status in (429, 403):
                        logger.warning("Rate-limit %d en %s (intento %d)", status, url, attempt + 1)
                        continue
                    if status >= 500:
                        logger.warning("Server error %d en %s", status, url)
                        continue
                    if wait_for_load:
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except Exception:  # noqa: BLE001
                            pass
                    html = await page.content()
                    return html
            except Exception as e:  # noqa: BLE001
                logger.warning("Error navegando a %s (intento %d): %s", url, attempt + 1, e)

        logger.error("Stealth fetch agotó reintentos para %s", url)
        return None

    async def head_ok(self, url: str, timeout_s: int = 5) -> tuple[bool, int | None]:
        """Lightweight availability check via a HEAD request (using aiohttp if available)."""
        try:
            import aiohttp  # type: ignore
        except ImportError:
            return True, None  # optimistic when we can't verify

        headers = {
            "User-Agent": random_user_agent(),
            "Accept-Language": random_accept_language(),
        }
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_s)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.head(url, allow_redirects=True) as resp:
                    return (200 <= resp.status < 400), resp.status
        except Exception as e:  # noqa: BLE001
            logger.debug("HEAD check falló %s: %s", url, e)
            return False, None
