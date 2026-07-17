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
from motor.core.web.models import Citation, SearchResult, SourceMetadata, WebDocument
from motor.core.web.pipeline import PipelineStage, WebPipeline
from motor.core.web.registry import Registry

__all__ = [
    "Citation",
    "Crawler",
    "Extractor",
    "PipelineStage",
    "Ranker",
    "Registry",
    "SearchProvider",
    "SearchResult",
    "SourceMetadata",
    "SourceValidator",
    "Summarizer",
    "WebConfig",
    "WebDocument",
    "WebPipeline",
]
