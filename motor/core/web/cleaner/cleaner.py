"""DocumentCleaner — normalización y limpieza de documentos web."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from motor.core.web.cleaner.url_utils import normalize_url

if TYPE_CHECKING:
    from motor.core.web.models import WebDocument


@dataclass
class CleanedStats:
    """Estadísticas del proceso de limpieza y deduplicación."""

    documents_received: int = 0
    documents_removed_empty: int = 0
    documents_removed_duplicate_url: int = 0
    documents_removed_duplicate_hash: int = 0
    documents_unique: int = 0

    @property
    def documents_removed(self) -> int:
        return (
            self.documents_removed_empty + self.documents_removed_duplicate_url + self.documents_removed_duplicate_hash
        )

    @property
    def duplication_pct(self) -> float:
        if self.documents_received == 0:
            return 0.0
        return round((self.documents_removed / self.documents_received) * 100, 1)

    def to_dict(self) -> dict:
        return {
            "documents_received": self.documents_received,
            "documents_removed": self.documents_removed,
            "documents_unique": self.documents_unique,
            "duplication_pct": self.duplication_pct,
            "removed_empty": self.documents_removed_empty,
            "removed_duplicate_url": self.documents_removed_duplicate_url,
            "removed_duplicate_hash": self.documents_removed_duplicate_hash,
        }


@dataclass
class CleanedResult:
    """Resultado del proceso de limpieza."""

    documents: list[WebDocument] = field(default_factory=list)
    stats: CleanedStats = field(default_factory=CleanedStats)


_MIN_WORDS = 3


class DocumentCleaner:
    """Limpieza y normalización de documentos.

    - Normaliza URLs (fragmentos, esquema, slash final)
    - Elimina documentos vacíos o con muy poco contenido
    """

    def __init__(self, min_words: int = _MIN_WORDS) -> None:
        self._min_words = min_words

    def clean(self, documents: list[WebDocument]) -> CleanedResult:
        stats = CleanedStats(documents_received=len(documents))
        cleaned: list[WebDocument] = []

        for doc in documents:
            doc.url = normalize_url(doc.url)
            text = (doc.text or "").strip()
            if not text or len(text.split()) < self._min_words:
                stats.documents_removed_empty += 1
                continue
            cleaned.append(doc)

        return CleanedResult(documents=cleaned, stats=stats)
