"""WebSearchIntegration — busca info actualizada cuando se detecta tendencia."""
from __future__ import annotations

from typing import Any

from motor.assistant.trends import TrendAwareness


class WebSearchIntegration:
    def __init__(self, trend_awareness: TrendAwareness | None = None) -> None:
        self._trends = trend_awareness or TrendAwareness()

    def search_if_needed(self, user_message: str, intent: str = "") -> dict[str, Any]:
        trend = self._trends.analyze_query(user_message, intent)
        if not trend.needs_update:
            return {"searched": False, "reason": trend.reason, "results": ""}

        results = self._search_web(user_message)
        return {
            "searched": True,
            "reason": trend.reason,
            "results": results,
            "suggested_sources": trend.suggested_sources,
        }

    def _search_web(self, query: str) -> str:
        try:
            import httpx

            response = httpx.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1},
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                abstract = data.get("AbstractText", "")
                source = data.get("AbstractSource", "")
                if abstract:
                    return f"Según {source}: {abstract[:500]}"
            return ""
        except Exception:
            return ""

    def is_available(self) -> bool:
        try:
            import httpx  # noqa: F401
            return True
        except ImportError:
            return False
