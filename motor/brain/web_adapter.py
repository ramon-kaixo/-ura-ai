"""Adaptador entre modulo web existente (motor.core.web) y cerebro."""

from __future__ import annotations

from typing import Any


class WebLearningAdapter:
    """Conecta motor.core.web con el cerebro."""

    def __init__(self) -> None:
        self._crawler: Any | None = None
        self._searcher: Any | None = None
        self._summarizer: Any | None = None

    def _load_modules(self) -> None:
        if self._crawler is None:
            from motor.core.web.crawler.providers.httpx_crawler import HttpCrawler

            self._crawler = HttpCrawler
        if self._searcher is None:
            from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider

            self._searcher = DuckDuckGoSearchProvider
        if self._summarizer is None:
            from motor.core.web.summarizer.summarizer import ExtractiveSummarizer

            self._summarizer = ExtractiveSummarizer

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        self._load_modules()
        if self._searcher is None:
            return [{"error": "No searcher available"}]
        try:
            provider = self._searcher()
            results = provider.search(query, max_results=max_results)
            return [
                {
                    "source": r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", "")[:300],
                    "relevance": self._score(query, r),
                }
                for r in (results or [])
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def crawl(self, url: str) -> dict[str, Any]:
        self._load_modules()
        if self._crawler is None:
            return {"error": "No crawler available"}
        try:
            doc = self._crawler().crawl(url)
            return {"url": url, "content": doc.content[:1000] if doc else "", "status": "ok"}
        except Exception as e:
            return {"url": url, "error": str(e), "status": "error"}

    def summarize(self, text: str, max_sentences: int = 5) -> str:
        self._load_modules()
        if self._summarizer is None:
            return "No summarizer available"
        try:
            summary = self._summarizer().summarize(text, max_sentences=max_sentences)
            return summary or ""
        except Exception:
            return ""

    def learn_from_web(self, query: str) -> dict[str, Any]:
        """Busca, crawlea y resume informacion sobre un tema."""
        results = self.search(query)
        crawled: list[dict[str, Any]] = []
        for r in results[:3]:
            if r.get("source"):
                crawled.append(self.crawl(r["source"]))
        combined = " ".join(c.get("content", "")[:500] for c in crawled if c.get("status") == "ok")
        summary = self.summarize(combined) if combined else ""
        return {
            "query": query,
            "sources_found": len(results),
            "sources_crawled": len(crawled),
            "summary": summary,
        }

    @staticmethod
    def _score(query: str, item: dict) -> float:
        text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
        words = query.lower().split()
        matches = sum(1 for w in words if w in text)
        return min(matches / len(words), 1.0) if words else 0.0
