"""Tests para knowledge/engine/chunker.py — fragmentación de documentos.

Funciones puras: chunk_document y chunk_text. Sin I/O ni mocks.
"""
from __future__ import annotations

from knowledge.engine.chunker import chunk_document, chunk_text
from knowledge.engine.models import CHUNK_OVERLAP_WORDS, MAX_CHUNK_WORDS, Chunk, Document, Frontmatter


def _doc(body: str, doc_id: str = "doc1", title: str = "Titulo") -> Document:
    return Document(
        doc_id=doc_id,
        doc_type="md",
        path="path/doc.md",
        content_sha256="abc",
        frontmatter=Frontmatter(title=title, doc_type="md"),
        body=body,
    )


class TestChunkDocument:
    def test_body_vacio(self) -> None:
        assert chunk_document(_doc("   ")) == []

    def test_body_corto_un_chunk(self) -> None:
        doc = _doc("hola mundo", title="Mi titulo")
        chunks = chunk_document(doc)
        assert len(chunks) == 1
        assert isinstance(chunks[0], Chunk)
        assert chunks[0].doc_id == "doc1"
        assert chunks[0].chunk_index == 0
        assert chunks[0].text == "hola mundo"
        assert chunks[0].title == "Mi titulo"
        assert chunks[0].doc_type == "md"
        assert chunks[0].path == "path/doc.md"

    def test_largo_divide_con_solapamiento(self) -> None:
        words = [f"palabra{i}" for i in range(120)]
        doc = _doc(" ".join(words))
        chunks = chunk_document(doc, max_words=50, overlap=10)
        assert len(chunks) == 3
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1
        assert chunks[2].chunk_index == 2
        assert len(chunks[0].text.split()) == 50
        assert len(chunks[1].text.split()) == 50
        assert len(chunks[2].text.split()) == 40
        overlap_words = set(chunks[0].text.split()[-10:]) & set(chunks[1].text.split()[:10])
        assert len(overlap_words) == 10

    def test_exacto_max_words_un_chunk(self) -> None:
        words = " ".join(f"w{i}" for i in range(50))
        chunks = chunk_document(_doc(words), max_words=50, overlap=5)
        assert len(chunks) == 1

    def test_defaults_constantes(self) -> None:
        words = " ".join(f"w{i}" for i in range(MAX_CHUNK_WORDS + 100))
        chunks = chunk_document(_doc(words))
        assert len(chunks) > 1
        assert len(chunks[0].text.split()) == MAX_CHUNK_WORDS

    def test_overlap_por_defecto(self) -> None:
        words = " ".join(f"w{i}" for i in range(150))
        chunks = chunk_document(_doc(words), max_words=100)
        overlap_real = set(chunks[0].text.split()[-CHUNK_OVERLAP_WORDS:]) & set(chunks[1].text.split()[:CHUNK_OVERLAP_WORDS])
        assert len(overlap_real) == CHUNK_OVERLAP_WORDS

    def test_overlap_mayor_que_max_no_cuelga(self) -> None:
        words = " ".join(f"w{i}" for i in range(100))
        chunks = chunk_document(_doc(words), max_words=50, overlap=60)
        assert len(chunks) > 1
        assert chunks[-1].chunk_index == len(chunks) - 1


class TestChunkText:
    def test_vacio(self) -> None:
        assert chunk_text("   ") == []

    def test_corto(self) -> None:
        chunks = chunk_text("hola", doc_id="x", doc_type="md", path="p.md", title="t")
        assert len(chunks) == 1
        assert chunks[0].text == "hola"
        assert chunks[0].doc_id == "x"
        assert chunks[0].title == "t"

    def test_largo(self) -> None:
        words = " ".join(f"w{i}" for i in range(80))
        chunks = chunk_text(words, max_words=30, overlap=5)
        assert len(chunks) == 3
        assert len(chunks[2].text.split()) == 30
