import asyncio
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

WHITELIST_DIRS = [
    Path("/home/ramon/URA/ura_ia_1972").resolve(),
    Path("/home/ramon/.nervioso").resolve(),
    Path("/home/ramon/URA").resolve(),
]

DEFAULT_ENGINE = os.environ.get("MOCHILA_DEFAULT_ENGINE", "duckduckgo")  # duckduckgo | searxng
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")  # SSH tunnel from Hetzner
SEARXNG_TIMEOUT = int(os.environ.get("MOCHILA_SEARXNG_TIMEOUT", "2"))  # corto: Alemania caido
DUCKDUCKGO_URL = os.environ.get("DUCKDUCKGO_URL", "https://lite.duckduckgo.com/lite")

HTTPS_PROXY = os.environ.get("HTTPS_PROXY", "")  # proxy via Hetzner
HTTP_PROXY = os.environ.get("HTTP_PROXY", "")
WEBSEARCH_TIMEOUT = int(os.environ.get("MOCHILA_WEBSEARCH_TIMEOUT", "15"))
PAGEREAD_TIMEOUT = int(os.environ.get("MOCHILA_PAGEREAD_TIMEOUT", "20"))
PAGEREAD_MAX_SIZE = int(os.environ.get("MOCHILA_PAGEREAD_MAX_SIZE", "50000"))
WEBSEARCH_INTERVAL = float(os.environ.get("MOCHILA_WEBSEARCH_INTERVAL", "1.0"))
_last_search: float = 0.0
_rate_limit_lock = asyncio.Lock()

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca informacion actualizada en internet",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Terminos de busqueda"},
                    "max_results": {"type": "integer", "description": "Maximo de resultados (1-10)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "page_read",
            "description": "Lee el contenido textual de una URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL completa a leer"},
                    "max_chars": {"type": "integer", "description": "Maximo de caracteres", "default": 50000},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Lee el contenido de un archivo local del proyecto URA",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta al archivo (absoluta o relativa a ura_ia_1972)"},
                    "max_lines": {"type": "integer", "description": "Maximo de lineas", "default": 200},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crawl_web",
            "description": "Raspa una web dinamica con JavaScript usando Crawl4AI",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL completa a raspar"},
                },
                "required": ["url"],
            },
        },
    },
]


def _en_whitelist(ruta: Path) -> bool:
    try:
        real = ruta.resolve()
        for w in WHITELIST_DIRS:
            try:
                real.relative_to(w)
                return True
            except ValueError:
                continue
        return False
    except (RuntimeError, OSError):
        return False


def _extraer_texto(html: str, max_chars: int = 50000) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


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
            results = []
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


async def _buscar_searxng(query: str, max_results: int = 5) -> dict:
    params = {"q": query, "format": "json", "language": "es,en", "categories": "general", "pageno": 1}
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


async def page_read(url: str, max_chars: int = 50000) -> dict:
    max_chars = min(max_chars, PAGEREAD_MAX_SIZE)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; URA/1.0)", "Accept": "text/html,*/*;q=0.8"}
    try:
        async with httpx.AsyncClient(timeout=PAGEREAD_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.is_error:
                return {"error": f"HTTP {resp.status_code} para: {url}", "url": url}
            content_type = resp.headers.get("content-type", "")
            if "text" not in content_type and "html" not in content_type:
                return {"error": f"Content-Type no soportado: {content_type}", "url": url}
            texto = _extraer_texto(resp.text, max_chars)
            return {
                "url": url,
                "status": resp.status_code,
                "content_length": len(resp.text),
                "extracted_length": len(texto),
                "content": texto,
            }
    except httpx.TimeoutException:
        return {"error": f"Timeout ({PAGEREAD_TIMEOUT}s) leyendo: {url}", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


async def file_read(path: str, max_lines: int = 200) -> dict:
    ruta = Path(path)
    if not ruta.is_absolute():
        ruta = Path("/home/ramon/URA/ura_ia_1972") / ruta
    if not _en_whitelist(ruta):
        return {"error": f"Acceso denegado: {path}", "path": path}
    if not ruta.exists():
        return {"error": f"Archivo no encontrado: {ruta}", "path": path}
    if not ruta.is_file():
        return {"error": f"No es un archivo: {ruta}", "path": path}
    try:
        with open(ruta, encoding="utf-8", errors="replace") as f:  # noqa: ASYNC230, PTH123
            lineas = []
            for i, linea in enumerate(f):
                if i >= max_lines:
                    lineas.append(f"... ({max_lines} lineas mostradas)")
                    break
                lineas.append(linea.rstrip("\n"))
        return {
            "path": str(ruta.resolve()),
            "lines": len(lineas),
            "size": ruta.stat().st_size,
            "content": "\n".join(lineas),
        }
    except OSError as e:
        return {"error": str(e), "path": path}


TOOL_HANDLERS: dict[str, Any] = {
    "web_search": web_search,
    "page_read": page_read,
    "file_read": file_read,
}


async def ejecutar_tool(name: str, arguments: dict) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"Tool desconocida: {name}"}
    return await handler(**arguments)


async def crawl_web(url: str, max_chars: int = 50000) -> dict:
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            if result.success:
                text = result.markdown[:max_chars] if result.markdown else result.text[:max_chars]
                return {"url": url, "status": 200, "content_length": len(text), "content": text}
            return {"error": f"Crawl4AI: {result.error}", "url": url}
    except ImportError:
        return {"error": "crawl4ai no instalado", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


# Register crawl_web after definition
TOOL_HANDLERS["crawl_web"] = crawl_web
