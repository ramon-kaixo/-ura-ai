import asyncio
import logging
import random

import httpx

log = logging.getLogger("ura.stealth_fetcher")

USER_AGENTS = [
"Mozilla/5.0 (Windows NT 10.0 "
"Win64 "
"x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
"Mozilla/5.0 (Macintosh "
"Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
"Mozilla/5.0 (Windows NT 10.0 "
"Win64 "
"x64 "
"rv:127.0) Gecko/20100101 Firefox/127.0",
"Mozilla/5.0 (X11 "
"Linux aarch64 "
"rv:127.0) Gecko/20100101 Firefox/127.0",
"Mozilla/5.0 (Macintosh "
"Intel Mac OS X 10.15 "
"rv:127.0) Gecko/20100101 Firefox/127.0",
"Mozilla/5.0 (Windows NT 10.0 "
"Win64 "
"x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
"Mozilla/5.0 (X11 "
"Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

DEFAULT_TIMEOUT = 30


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _default_headers() -> dict:
    return {
        "User-Agent": _random_ua(),
"Accept": "text/html,application/xhtml+xml,application/xml "
"q=0.9,*/* "
"q=0.8",
"Accept-Language": "es-ES,es "
"q=0.9,en "
"q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


async def fetch(url: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    headers = _default_headers()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.is_error:
                return None
            return resp.text
    except Exception:
        log.exception("fetch_plain failed for %s", url)
        return None


async def fetch_stealth(url: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    try:
        from playwright.async_api import async_playwright

        ua = _random_ua()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=ua,
                viewport={"width": 1920, "height": 1080},
                locale="es-ES",
                timezone_id="Europe/Madrid",
            )
            try:
                from playwright_stealth import stealth_async

                page = await context.new_page()
                try:
                    await stealth_async(page)
                    await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                    return await page.content()
                except Exception:
                    log.warning("stealth goto failed for %s, falling back", url)
                    await page.close()
                    try:
                        page = await context.new_page()
                        await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                        return await page.content()
                    except Exception:
                        log.warning("fallback goto also failed for %s", url)
                        return None
            except ImportError:
                return None
            finally:
                if page:
                    await page.close()
                await browser.close()
    except ImportError:
        return None
    except Exception:
        log.exception("fetch_stealth failed for %s", url)
        return None


async def fetch_with_fallback(url: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    result = await fetch_stealth(url, timeout)
    if result:
        return result
    await asyncio.sleep(1)
    return await fetch(url, timeout)
