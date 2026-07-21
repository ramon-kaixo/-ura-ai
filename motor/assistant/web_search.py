"""WebSearch — búsqueda web real integrada en el asistente."""

from __future__ import annotations

import re
from typing import Any

import httpx


class WebSearch:
    def __init__(self, timeout: int = 10):
        self._timeout = timeout

    async def search(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "URA-Assistant/1.0"},
                )
                if resp.status_code != 200:
                    return []
                return self._parse_results(resp.text, max_results)
        except Exception:
            return []

    def _parse_results(self, html: str, max_results: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for line in html.split("\n"):
            if 'class="result__a"' in line:
                title_match = re.search(r">(.*?)<", line)
                title = title_match.group(1) if title_match else ""
                results.append({"title": title, "snippet": ""})
            if 'class="result__snippet"' in line:
                snippet_match = re.search(r">(.*?)<", line)
                if results:
                    results[-1]["snippet"] = snippet_match.group(1) if snippet_match else ""
            if len(results) >= max_results:
                break
        return results
