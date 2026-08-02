"""Tests para core/chunking.py — chunking semantico y ventana de palabras."""
from __future__ import annotations

import pytest

from core.chunking import _split_paragraphs, _split_sections, _word_window, chunk_semantic


class TestChunkSemantic:
    def test_texto_vacio(self) -> None:
        assert chunk_semantic("") == [""]  # fallback window con vacio

    def test_seccion_corta(self) -> None:
        texto = "# Título\n\nPárrafo corto."
        chunks = chunk_semantic(texto, max_words=500)
        assert len(chunks) == 1
        assert "Título" in chunks[0]

    def test_secion_larga_se_parteciona(self) -> None:
        parrafo1 = " ".join(["palabra"] * 80)
        parrafo2 = " ".join(["otra"] * 80)
        texto = f"# Sección\n\n{parrafo1}\n\n{parrafo2}"
        chunks = chunk_semantic(texto, max_words=100, min_words=50)
        assert len(chunks) >= 1
        # El chunking respeta las secciones
        total_words = sum(len(c.split()) for c in chunks)
        assert total_words == 162  # 80 + 80 + titulo (2 palabras)

    def test_fallback_ventana(self) -> None:
        texto = " ".join(["w"] * 250)
        chunks = chunk_semantic(texto, max_words=100, min_words=50)
        assert len(chunks) == 3  # 100 + 100 + 50 (overlap 10)
        assert all(len(c.split()) <= 100 for c in chunks)


class TestSplitSections:
    def test_markdown_headings(self) -> None:
        texto = "intro\n\n# Uno\n\ncontenido uno\n\n## Dos\n\ncontenido dos"
        secciones = _split_sections(texto)
        assert len(secciones) >= 3

    def test_secciones_limpias(self) -> None:
        texto = "# A\n\ntexto a\n# B\n\ntexto b"
        secciones = _split_sections(texto)
        assert all(s == s.strip() for s in secciones)
        assert all(s for s in secciones)

    def test_sin_secciones(self) -> None:
        texto = "solo texto plano sin estructura"
        secciones = _split_sections(texto)
        assert len(secciones) == 1


class TestSplitParagraphs:
    def test_agrupa_parrafos(self) -> None:
        p1 = " ".join(["a"] * 40)
        p2 = " ".join(["b"] * 40)
        texto = f"{p1}\n\n{p2}"
        chunks = _split_paragraphs(texto, max_words=100, min_words=50)
        assert len(chunks) == 1
        assert len(chunks[0].split()) == 80

    def test_parrafo_excede_max(self) -> None:
        p = " ".join(["x"] * 60)
        chunks = _split_paragraphs(p, max_words=30, min_words=10)
        assert len(chunks) >= 2

    def test_buffer_menor_que_min_se_anexa(self) -> None:
        p1 = " ".join(["a"] * 60)
        p2 = " ".join(["b"] * 10)  # 10 palabras < min_words 20
        texto = f"{p1}\n\n{p2}"
        chunks = _split_paragraphs(texto, max_words=100, min_words=20)
        assert len(chunks) == 1
        assert "a" in chunks[0] and "b" in chunks[0]

    def test_buffer_sin_chunks_previos(self) -> None:
        p = " ".join(["z"] * 10)
        chunks = _split_paragraphs(p, max_words=100, min_words=50)
        assert len(chunks) == 1  # buffer se anexa aun sin llegar a min


class TestWordWindow:
    def test_menor_que_size(self) -> None:
        assert _word_window("hola mundo", 10, 2) == ["hola mundo"]

    def test_divide_con_overlap(self) -> None:
        texto = " ".join(["w"] * 25)
        chunks = _word_window(texto, 10, 5)
        assert len(chunks) == 5  # starts 0,5,10,15,20
        assert all(len(c.split()) <= 10 for c in chunks)

    def test_solapa_contenido(self) -> None:
        texto = " ".join(str(i) for i in range(15))
        chunks = _word_window(texto, 10, 5)
        assert "5 6" in chunks[1]  # overlap contiene palabras del chunk anterior

    def test_vacio(self) -> None:
        assert _word_window("", 10, 2) == [""]
