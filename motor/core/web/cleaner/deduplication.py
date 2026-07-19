"""DeduplicationEngine — eliminación de duplicados por URL, canonical_id y contenido."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from motor.core.web.cleaner.url_utils import content_hash, get_document_id, normalize_url

if TYPE_CHECKING:
    from motor.core.web.cleaner.cleaner import CleanedStats
    from motor.core.web.models import WebDocument


class _State:
    """Estado mutable del proceso de deduplicación."""

    __slots__ = ("hash_best", "id_best", "seen_ids", "stats", "url_best")

    def __init__(self, stats: CleanedStats | None) -> None:
        self.url_best: dict[str, WebDocument] = {}
        self.id_best: dict[str, WebDocument] = {}
        self.hash_best: dict[str, WebDocument] = {}
        self.seen_ids: set[int] = set()
        self.stats = stats


def _try_add(
    doc: WebDocument,
    norm_url: str,
    doc_id: str,
    h: str,
    state: _State,
) -> bool:
    """Intenta añadir el documento si no hay duplicado. Retorna True si se añadió."""
    # URL match
    existing = state.url_best.get(norm_url)
    if existing is not None:
        _handle_dup(doc, existing, state, "url")
        return False

    # doc_id match
    existing = state.id_best.get(doc_id)
    if existing is not None:
        _handle_dup(doc, existing, state, "url")
        return False

    # hash match
    existing = state.hash_best.get(h)
    if existing is not None:
        _handle_dup(doc, existing, state, "hash")
        return False

    # Nuevo documento
    state.url_best[norm_url] = doc
    state.id_best[doc_id] = doc
    state.hash_best[h] = doc
    state.seen_ids.add(id(doc))
    return True


def _handle_dup(
    doc: WebDocument,
    existing: WebDocument,
    state: _State,
    kind: str,
) -> None:
    """Maneja un duplicado: si doc tiene mejor calidad, reemplaza."""
    if doc.quality_score > existing.quality_score:
        _remove_doc(existing, state)
        norm_url = normalize_url(doc.url)
        canonical = (
            doc.metadata.get("canonical_url")
            if isinstance(doc.metadata, dict)
            else None
        )
        doc_id = get_document_id(doc.url, canonical)
        h = content_hash(doc.text or "")
        state.url_best[norm_url] = doc
        state.id_best[doc_id] = doc
        state.hash_best[h] = doc
        state.seen_ids.add(id(doc))
    if state.stats is not None:
        if kind == "hash":
            state.stats.documents_removed_duplicate_hash += 1
        else:
            state.stats.documents_removed_duplicate_url += 1


def _remove_doc(doc: WebDocument, state: _State) -> None:
    """Elimina un documento de todos los índices."""
    norm_url = normalize_url(doc.url)
    canonical = (
        doc.metadata.get("canonical_url")
        if isinstance(doc.metadata, dict)
        else None
    )
    doc_id = get_document_id(doc.url, canonical)
    h = content_hash(doc.text or "")

    if state.url_best.get(norm_url) is doc:
        del state.url_best[norm_url]
    if state.id_best.get(doc_id) is doc:
        del state.id_best[doc_id]
    if state.hash_best.get(h) is doc:
        del state.hash_best[h]
    state.seen_ids.discard(id(doc))


class DeduplicationEngine:
    """Eliminación de duplicados con tres estrategias:

    1. URL exacta (normalizada)
    2. document_id (URL canónica)
    3. content_hash (SHA-256 del texto)

    Cuando hay duplicados, conserva el de mayor quality_score.
    Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def deduplicate(
        self,
        documents: list[WebDocument],
        stats: CleanedStats | None = None,
    ) -> list[WebDocument]:
        """Elimina duplicados y devuelve documentos únicos."""
        with self._lock:
            state = _State(stats)

            for doc in documents:
                norm_url = normalize_url(doc.url)
                canonical = (
                    doc.metadata.get("canonical_url")
                    if isinstance(doc.metadata, dict)
                    else None
                )
                doc_id = get_document_id(doc.url, canonical)
                h = content_hash(doc.text or "")
                _try_add(doc, norm_url, doc_id, h, state)

            result = [d for d in documents if id(d) in state.seen_ids]
            if stats is not None:
                stats.documents_unique = len(result)

            return result
