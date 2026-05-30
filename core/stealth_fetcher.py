#!/usr/bin/env python3
"""
Stealth Fetcher — Descarga la página y extrae texto principal.

API simple:

    text, final_url = await fetch_page(url)

Diseñado como complemento al `core.ura_stealth_browser.StealthBrowser` que
trabaja a más bajo nivel devolviendo HTML. Aquí extraemos texto limpio
con BeautifulSoup eliminando script/style/nav/footer y normalizando
espacios. Útil para expandir snippets en `SearchOrchestrator`.

Sin Docker. Solo Playwright + bs4 instalados con pip.
"""

from __future__ import annotations

import asyncio
import logging
import random

logger = logging.getLogger("stealth_fetcher")

try:
    from playwright.async_api import async_playwright  # type: ignore

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    async_playwright = None  # type: ignore

try:
    from bs4 import BeautifulSoup  # type: ignore

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    BeautifulSoup = None  # type: ignore

# UAs reutilizamos los del stealth_browser para coherencia
from core.ura_stealth_browser import (
    random_user_agent,
    random_accept_language,
)

DEFAULT_TIMEOUT_MS = 15_000
MIN_JITTER = 1.0
MAX_JITTER = 3.5

_TAGS_TO_REMOVE = (
    "script",
    "style",
    "noscript",
    "iframe",
    "form",
    "header",
    "footer",
    "nav",
    "aside",
)


async def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT_MS) -> tuple[str, str | None]:
    """
    Navega a `url` con Playwright en headless y devuelve `(texto_limpio, url_final)`.

    Devuelve `("", None)` si Playwright no está instalado o si la página falla.
    """
    if not HAS_PLAYWRIGHT:
        logger.error("Playwright no está instalado")
        return "", None
    if not HAS_BS4:
        logger.error("beautifulsoup4 no está instalado")
        return "", None

    await asyncio.sleep(random.uniform(MIN_JITTER, MAX_JITTER))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=random_user_agent(),
                locale="es-ES",
                viewport={"width": 1366, "height": 768},
                extra_http_headers={"Accept-Language": random_accept_language()},
            )
            page = await context.new_page()
            page.set_default_timeout(timeout)

            try:
                response = await page.goto(url, wait_until="domcontentloaded")
            except Exception as e:  # noqa: BLE001
                logger.warning("fetch_page error navegando a %s: %s", url, e)
                return "", None

            if response is None or response.status >= 400:
                logger.warning("fetch_page status incorrecto para %s", url)
                return "", None

            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:  # noqa: BLE001
                pass  # mejor seguir con lo que tengamos

            html = await page.content()
            final_url = page.url

            text = _extract_main_text(html)
            return text, final_url
        finally:
            await browser.close()


def _extract_main_text(html: str) -> str:
    """Limpia HTML y devuelve solo el texto principal."""
    if not html or not HAS_BS4:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in _TAGS_TO_REMOVE:
        for el in soup.find_all(tag_name):
            el.decompose()

    # Preferimos <main> o <article> si existen
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator=" ", strip=True)
    # Normalizar espacios
    return " ".join(text.split())
