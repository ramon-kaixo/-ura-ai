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
from motor.core.web.citation.citation import (
    CitationBundle,
    CitationEngine,
    CitationRecord,
    Evidence,
    make_evidence_id,
)
from motor.core.web.cleaner.cleaner import CleanedResult, CleanedStats, DocumentCleaner
from motor.core.web.cleaner.deduplication import DeduplicationEngine
from motor.core.web.cleaner.url_utils import content_hash, normalize_url
from motor.core.web.config import WebConfig
from motor.core.web.crawler.providers.httpx_crawler import CrawledDocument, HttpCrawler
from motor.core.web.extractor.providers.html_extractor import HtmlExtractor
from motor.core.web.models import Citation, SearchResult, SourceMetadata, WebDocument
from motor.core.web.pipeline import PipelineStage, WebPipeline
from motor.core.web.ranker.ranker import DocumentRanker, RankedDocument, RankingScore
from motor.core.web.registry import Registry
from motor.core.web.searcher.providers.duckduckgo import DuckDuckGoSearchProvider
from motor.core.web.searcher.providers.searxng import SearXNGSearchProvider
from motor.core.web.summarizer.summarizer import (
    ExtractiveSummarizer,
    SentenceInfo,
    Summary,
    split_sentences,
)

__all__ = [
    "Citation",
    "CitationBundle",
    "CitationEngine",
    "CitationRecord",
    "CleanedResult",
    "CleanedStats",
    "CrawledDocument",
    "Crawler",
    "DeduplicationEngine",
    "DocumentCleaner",
    "DocumentRanker",
    "DuckDuckGoSearchProvider",
    "Evidence",
    "ExtractiveSummarizer",
    "Extractor",
    "HtmlExtractor",
    "HttpCrawler",
    "PipelineStage",
    "RankedDocument",
    "Ranker",
    "RankingScore",
    "Registry",
    "SearXNGSearchProvider",
    "SearchProvider",
    "SearchResult",
    "SentenceInfo",
    "SourceMetadata",
    "SourceValidator",
    "Summarizer",
    "Summary",
    "WebConfig",
    "WebDocument",
    "WebPipeline",
    "content_hash",
    "make_evidence_id",
    "normalize_url",
    "split_sentences",
]
