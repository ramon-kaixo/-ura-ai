"""web_search — Búsqueda web determinista (DDG + SearXNG con fallback).

Definición canónica en motor/ (capa inferior). `core/mochila/tools.py`
reexporta estas funciones como fachada para preservar compatibilidad.
Sin dependencias de core (solo stdlib + httpx).
"""

from __future__ import annotations

import asyncio
import os
import re
import time

import httpx

DEFAULT_ENGINE = os.environ.get("MOCHILA_DEFAULT_ENGINE", "duckduckgo")  # duckduckgo | searxng
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")  # SSH tunnel from Hetzner
SEARXNG_TIMEOUT = int(os.environ.get("MOCHILA_SEARXNG_TIMEOUT", "2"))  # corto: Alemania caido
DUCKDUCKGO_URL = os.environ.get("DUCKDUCKGO_URL", "https://lite.duckduckgo.com/lite")
WEBSEARCH_INTERVAL = float(os.environ.get("MOCHILA_WEBSEARCH_INTERVAL", "1.0"))
_last_search: float = 0.0
_rate_limit_lock = asyncio.Lock()


async def _buscar_ddg(query: str, max_results: int = 5) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                DUCKDUCKGO_URL,
                data={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; URA/1.0)",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                follow_redirects=True,
            )
            if resp.is_error:
                return {"error": f"DDG error: {resp.status_code}", "query": query}
            text = resp.text.replace("\n", " ")
            results: list[dict[str, str]] = []
            for m in re.finditer(
                r'<a[^>]*rel="nofollow"[^>]*href="([^"]*)"[^>]*class=\'result-link\'[^>]*>(.*?)</a>',
                text,
            ):
                if len(results) >= max_results:
                    break
                url = m.group(1)
                title = re.sub(r"<[^>]*>", "", m.group(2)).strip()
                title = re.sub(r"&#x27;", "'", title)
                title = re.sub(r"&[a-z]+;", " ", title)
                results.append({"title": title[:150], "url": url, "snippet": ""})
            for m2 in re.finditer(r"<td class='result-snippet'>(.*?)</td>", text):
                filled = sum(1 for r in results if r["snippet"])
                if filled < len(results):
                    snippet = re.sub(r"<[^>]*>", "", m2.group(1)).strip()
                    snippet = re.sub(r"&#x27;", "'", snippet)
                    snippet = re.sub(r"&[a-z]+;", " ", snippet)
                    snippet = re.sub(r"\s+", " ", snippet)
                    results[filled]["snippet"] = snippet[:500]
            return {"query": query, "total_results": len(results), "results": results}
    except Exception as e:
        return {"error": str(e), "query": query}


async def _buscar_searxng(query: str, max_results: int = 5) -> dict:
    params: dict[str, str | int] = {"q": query, "format": "json", "language": "es,en", "categories": "general", "pageno": 1}
    try:
        async with httpx.AsyncClient(timeout=SEARXNG_TIMEOUT) as client:
            resp = await client.get(f"{SEARXNG_URL}/search", params=params)
            if resp.is_error:
                return {"error": f"SearXNG error: {resp.status_code}", "query": query}
            data = resp.json()
            results = data.get("results", [])[:max_results]
            return {
                "query": query,
                "total_results": len(results),
                "results": [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
                    for r in results
                ],
            }
    except httpx.TimeoutException:
        return {"error": "SearXNG timeout", "query": query}
    except Exception:
        return {"error": "SearXNG error", "query": query}


async def web_search(query: str, max_results: int = 5) -> dict:
    global _last_search  # noqa: PLW0603
    async with _rate_limit_lock:
        ahora = time.time()
        if ahora - _last_search < WEBSEARCH_INTERVAL:
            await asyncio.sleep(WEBSEARCH_INTERVAL - (ahora - _last_search))
        _last_search = ahora

    if DEFAULT_ENGINE == "duckduckgo":
        ddg = await _buscar_ddg(query, max_results)
        if "error" not in ddg:
            return ddg
        fallback = await _buscar_searxng(query, max_results)
        if "error" not in fallback:
            return fallback
        return ddg
    sx = await _buscar_searxng(query, max_results)
    if "error" not in sx:
        return sx
    ddg = await _buscar_ddg(query, max_results)
    if "error" not in ddg:
        return ddg
    return sx
