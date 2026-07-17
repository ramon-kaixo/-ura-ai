"""Web Intelligence (F24).

Módulo de búsqueda, extracción, procesamiento y síntesis de información web.
"""

from motor.core.web.base import (
    Crawler,
    Extractor,
    Ranker,
    SearchProvider,
    SourceValidator,
    Summarizer,
)
from motor.core.web.config import WebConfig
from motor.core.web.crawler.providers.httpx_crawler import CrawledDocument, HttpCrawler
from motor.core.web.extractor.providers.html_extractor import HtmlExtractor
from motor.core.web.models import Citation, SearchResult, SourceMetadata, WebDocument
from motor.core.web.pipeline import PipelineStage, WebPipeline
from motor.core.web.registry import Registry
from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider
from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider

__all__ = [
    "Citation",
    "CrawledDocument",
    "Crawler",
    "DuckDuckGoSearchProvider",
    "Extractor",
    "HtmlExtractor",
    "HttpCrawler",
    "PipelineStage",
    "Ranker",
    "Registry",
    "SearXNGSearchProvider",
    "SearchProvider",
    "SearchResult",
    "SourceMetadata",
    "SourceValidator",
    "Summarizer",
    "WebConfig",
    "WebDocument",
    "WebPipeline",
]
