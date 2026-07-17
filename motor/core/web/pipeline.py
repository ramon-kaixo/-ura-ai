"""Pipeline de Web Intelligence.

Orquesta el flujo completo: búsqueda → crawl → extracción → ranking → resumen.
"""

from __future__ import annotations

import logging
import time
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.core.web.models import Citation, SearchResult, WebDocument

log = logging.getLogger(__name__)


class PipelineStage(StrEnum):
    SEARCH = "search"
    CRAWL = "crawl"
    EXTRACT = "extract"
    CLEAN = "clean"
    RANK = "rank"
    SUMMARIZE = "summarize"
    VALIDATE = "validate"


class WebPipeline:
    """Pipeline completo de Web Intelligence.

    Orquesta buscadores, crawlers, extractores, rankers, summarizers
    y validadores registrados en el Registry.
    """

    def __init__(self, registry: Any) -> None:  # Registry type
        self._registry = registry
        self._stage_times: dict[PipelineStage, float] = {}

    @property
    def registry(self) -> Any:
        return self._registry

    def search(
        self,
        query: str,
        sources: list[str] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Ejecuta búsqueda en las fuentes indicadas."""
        t0 = time.monotonic()
        all_results: list[SearchResult] = []
        searchers = sources or self._registry.list_searchers()

        for name in searchers:
            try:
                searcher = self._registry.get_searcher(name)
                results = searcher.search(query, limit=limit)
                all_results.extend(results)
            except KeyError:
                continue

        self._stage_times[PipelineStage.SEARCH] = (time.monotonic() - t0) * 1000
        return all_results

    def fetch(self, url: str, crawler: str = "httpx") -> str:
        """Obtiene el HTML de una URL usando el crawler indicado."""
        t0 = time.monotonic()
        c = self._registry.get_crawler(crawler)
        html = c.fetch(url)
        self._stage_times[PipelineStage.CRAWL] = (time.monotonic() - t0) * 1000
        return html

    def extract(self, html: str, url: str, extractor: str = "readability") -> WebDocument:
        """Extrae contenido estructurado desde HTML."""
        t0 = time.monotonic()
        e = self._registry.get_extractor(extractor)
        doc = e.extract(html, url)
        self._stage_times[PipelineStage.EXTRACT] = (time.monotonic() - t0) * 1000
        return doc

    def rank(self, results: list[SearchResult], query: str) -> list[SearchResult]:
        """Ordena resultados según relevancia."""
        t0 = time.monotonic()
        ranker = self._registry.get_ranker("default")
        ranked = ranker.rank(results, query)
        self._stage_times[PipelineStage.RANK] = (time.monotonic() - t0) * 1000
        return ranked

    def summarize(
        self,
        query: str,
        documents: list[WebDocument],
    ) -> tuple[str, list[Citation]]:
        """Genera resumen con citas."""
        t0 = time.monotonic()
        summarizer = self._registry.get_summarizer("llm")
        summary, citations = summarizer.summarize(query, documents)
        self._stage_times[PipelineStage.SUMMARIZE] = (time.monotonic() - t0) * 1000
        return summary, citations

    def run(
        self,
        query: str,
        sources: list[str] | None = None,
        limit: int = 10,
        *,
        extract: bool = True,
        summarize: bool = True,
        crawler: str = "httpx",
        extractor: str = "readability",
    ) -> dict[str, Any]:
        """Ejecuta el pipeline completo."""
        t0 = time.monotonic()
        results: dict[str, Any] = {"query": query, "results": [], "summary": None, "citations": []}

        # 1. Search
        search_results = self.search(query, sources=sources, limit=limit)
        results["search_results"] = [r.to_dict() for r in search_results]

        if not extract and not summarize:
            results["elapsed_ms"] = (time.monotonic() - t0) * 1000
            results["stage_times"] = {k.value: round(v, 1) for k, v in self._stage_times.items()}
            return results

        # 2. Crawl + Extract for top results
        documents: list[WebDocument] = []
        for sr in search_results[:limit]:
            try:
                html = self.fetch(sr.url, crawler=crawler)
                doc = self.extract(html, sr.url, extractor=extractor)
                documents.append(doc)
                results["results"].append(doc.to_dict())
            except Exception as exc:
                log.debug("Error fetching/extracting %s: %s", sr.url, exc)
                continue

        # 3. Summarize
        if summarize and documents:
            summary, citations = self.summarize(query, documents)
            results["summary"] = summary
            results["citations"] = [c.to_dict() for c in citations]

        results["elapsed_ms"] = (time.monotonic() - t0) * 1000
        results["stage_times"] = {k.value: round(v, 1) for k, v in self._stage_times.items()}
        return results
