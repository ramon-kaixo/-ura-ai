"""Registry de proveedores del módulo Web Intelligence.

Gestiona el ciclo de vida de buscadores, crawlers, extractores,
rankers, summarizers y validadores registrados.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.web.base import (
        Crawler,
        Extractor,
        Ranker,
        SearchProvider,
        SourceValidator,
        Summarizer,
    )


class Registry:
    """Registro de proveedores web. Thread-safe por naturaleza.

    Mantiene listas separadas por tipo de proveedor.
    """

    def __init__(self) -> None:
        self._searchers: dict[str, SearchProvider] = {}
        self._crawlers: dict[str, Crawler] = {}
        self._extractors: dict[str, Extractor] = {}
        self._rankers: dict[str, Ranker] = {}
        self._summarizers: dict[str, Summarizer] = {}
        self._validators: dict[str, SourceValidator] = {}

    # ── Searchers ─────────────────────────────────────

    def register_searcher(self, name: str, provider: SearchProvider) -> None:
        self._searchers[name] = provider

    def get_searcher(self, name: str) -> SearchProvider:
        if name not in self._searchers:
            raise KeyError(f"Searcher '{name}' not found")
        return self._searchers[name]

    def list_searchers(self) -> list[str]:
        return list(self._searchers)

    # ── Crawlers ──────────────────────────────────────

    def register_crawler(self, name: str, provider: Crawler) -> None:
        self._crawlers[name] = provider

    def get_crawler(self, name: str) -> Crawler:
        if name not in self._crawlers:
            raise KeyError(f"Crawler '{name}' not found")
        return self._crawlers[name]

    def list_crawlers(self) -> list[str]:
        return list(self._crawlers)

    # ── Extractors ────────────────────────────────────

    def register_extractor(self, name: str, provider: Extractor) -> None:
        self._extractors[name] = provider

    def get_extractor(self, name: str) -> Extractor:
        if name not in self._extractors:
            raise KeyError(f"Extractor '{name}' not found")
        return self._extractors[name]

    def list_extractors(self) -> list[str]:
        return list(self._extractors)

    # ── Rankers ───────────────────────────────────────

    def register_ranker(self, name: str, provider: Ranker) -> None:
        self._rankers[name] = provider

    def get_ranker(self, name: str) -> Ranker:
        if name not in self._rankers:
            raise KeyError(f"Ranker '{name}' not found")
        return self._rankers[name]

    def list_rankers(self) -> list[str]:
        return list(self._rankers)

    # ── Summarizers ───────────────────────────────────

    def register_summarizer(self, name: str, provider: Summarizer) -> None:
        self._summarizers[name] = provider

    def get_summarizer(self, name: str) -> Summarizer:
        if name not in self._summarizers:
            raise KeyError(f"Summarizer '{name}' not found")
        return self._summarizers[name]

    def list_summarizers(self) -> list[str]:
        return list(self._summarizers)

    # ── Validators ────────────────────────────────────

    def register_validator(self, name: str, provider: SourceValidator) -> None:
        self._validators[name] = provider

    def get_validator(self, name: str) -> SourceValidator:
        if name not in self._validators:
            raise KeyError(f"Validator '{name}' not found")
        return self._validators[name]

    def list_validators(self) -> list[str]:
        return list(self._validators)
