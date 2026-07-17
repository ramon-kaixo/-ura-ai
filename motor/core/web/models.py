"""Modelos de datos del módulo Web Intelligence.

Define las estructuras de datos compartidas entre todos los componentes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """Resultado de una búsqueda web."""

    title: str
    url: str
    snippet: str
    source: str
    score: float = 0.0
    published: str | None = None
    language: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "score": self.score,
            "published": self.published,
        }


@dataclass
class SourceMetadata:
    """Metadatos de la fuente de un documento."""

    url: str
    domain: str
    fetch_time_ms: float = 0.0
    content_type: str | None = None
    content_length: int = 0
    status_code: int = 200
    error: str | None = None


@dataclass
class WebDocument:
    """Documento web extraído y procesado."""

    url: str
    title: str
    html: str = ""
    text: str = ""
    markdown: str = ""
    metadata: SourceMetadata | None = None
    readability_score: float = 0.0
    word_count: int = 0
    language: str | None = None
    extracted_at: float = field(default_factory=time.time)
    quality_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text[:500] if self.text else "",
            "markdown": self.markdown[:500] if self.markdown else "",
            "word_count": self.word_count,
            "language": self.language,
            "quality_score": self.quality_score,
        }


@dataclass
class Citation:
    """Cita con trazabilidad a la fuente original."""

    text: str
    url: str
    title: str
    source: str
    fragment: str = ""
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text[:200],
            "url": self.url,
            "title": self.title,
            "source": self.source,
            "confidence": self.confidence,
        }
