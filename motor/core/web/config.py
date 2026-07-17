"""Configuración del módulo Web Intelligence."""

from __future__ import annotations

from typing import Any


class WebConfig:
    """Configuración del módulo web.

    Los valores pueden sobrescribirse desde CONFIG o secrets.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}

        self.default_searcher: str = cfg.get("default_searcher", "duckduckgo")
        self.default_crawler: str = cfg.get("default_crawler", "httpx")
        self.default_extractor: str = cfg.get("default_extractor", "readability")
        self.default_ranker: str = cfg.get("default_ranker", "default")
        self.default_summarizer: str = cfg.get("default_summarizer", "llm")

        self.search_timeout: int = int(cfg.get("search_timeout", "10"))
        self.crawl_timeout: int = int(cfg.get("crawl_timeout", "30"))
        self.extract_timeout: int = int(cfg.get("extract_timeout", "15"))

        self.max_results_per_source: int = int(cfg.get("max_results_per_source", "10"))
        self.max_documents_to_summarize: int = int(cfg.get("max_documents_to_summarize", "5"))

        self.user_agent: str = cfg.get(
            "user_agent",
            "URA/1.0 (+https://github.com/anomalyco/ura) Web Intelligence",
        )

        self.robots_txt_cache_ttl: int = int(cfg.get("robots_txt_cache_ttl", "3600"))
        self.respect_robots_txt: bool = cfg.get("respect_robots_txt", True)
