"""Chunker — divide Document en fragmentos para embedding semántico.

Estrategia actual: sliding window de palabras con solapamiento.
Futuro: chunking semántico por límites de párrafo/sección.
"""

from __future__ import annotations

from knowledge.engine.models import CHUNK_OVERLAP_WORDS, MAX_CHUNK_WORDS, Chunk, Document


def chunk_document(
    doc: Document,
    max_words: int = MAX_CHUNK_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[Chunk]:
    """Divide un Document en fragmentos solapados.

    El body se particiona en ventanas de *max_words* palabras
    con *overlap* palabras de solapamiento entre ventanas.
    Cada Chunk conserva metadatos del documento padre.

    Si el body es más corto que max_words, retorna un solo Chunk.
    """
    if not doc.body.strip():
        return []

    words = doc.body.split()
    chunks: list[Chunk] = []
    title = doc.frontmatter.title or ""

    if len(words) <= max_words:
        return [
            Chunk(
                doc_id=doc.doc_id,
                chunk_index=0,
                text=doc.body,
                doc_type=doc.doc_type,
                path=doc.path,
                title=title,
            )
        ]

    start = 0
    index = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append(
            Chunk(
                doc_id=doc.doc_id,
                chunk_index=index,
                text=chunk_text,
                doc_type=doc.doc_type,
                path=doc.path,
                title=title,
            )
        )
        index += 1
        if end >= len(words):
            break
        start += max_words - overlap

    return chunks


def chunk_text(
    text: str,
    doc_id: str = "",
    doc_type: str = "",
    path: str = "",
    title: str = "",
    max_words: int = MAX_CHUNK_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[Chunk]:
    """Versión directa sin Document — útil para tests o textos sueltos."""
    words = text.split()
    if not words:
        return []

    if len(words) <= max_words:
        return [Chunk(doc_id=doc_id, chunk_index=0, text=text, doc_type=doc_type, path=path, title=title)]

    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(
            Chunk(
                doc_id=doc_id,
                chunk_index=index,
                text=" ".join(words[start:end]),
                doc_type=doc_type,
                path=path,
                title=title,
            )
        )
        index += 1
        if end >= len(words):
            break
        start += max_words - overlap
    return chunks
