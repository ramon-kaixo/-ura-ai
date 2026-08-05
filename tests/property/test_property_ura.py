"""Tests property-based (hypothesis) — propiedades universales del proyecto.

Cada test verifica una PROPIEDAD que debe cumplirse para CUALQUIER entrada,
no casos concretos. Hypothesis genera cientos de casos incluyendo edge cases.
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from knowledge.engine.chunker import chunk_text
from motor.core.llm._logging import percentile
from motor.core.qdrant_client import generar_sparse_vector
from scripts.pro.auditoria_continua import detectar_regresiones
from scripts.pro.tuneladora.pipeline.runner import _parse_coverage_output


class TestSparseVector:
    @settings(max_examples=100, deadline=1000)
    @given(st.text(min_size=0, max_size=500))
    def test_indices_no_negativos(self, texto: str) -> None:
        result = generar_sparse_vector(texto)
        assert all(i >= 0 for i in result["indices"])
        assert len(result["indices"]) == len(result["values"])

    @settings(max_examples=100, deadline=1000)
    @given(st.text(min_size=0, max_size=500))
    def test_valores_suman_uno(self, texto: str) -> None:
        result = generar_sparse_vector(texto)
        if result["indices"]:
            assert abs(sum(result["values"]) - 1.0) < 1e-9

    @settings(max_examples=100, deadline=1000)
    @given(st.text(min_size=0, max_size=500), st.integers(min_value=1, max_value=50))
    def test_max_tokens_respetado(self, texto: str, max_tokens: int) -> None:
        result = generar_sparse_vector(texto, max_tokens=max_tokens)
        assert len(result["indices"]) <= max_tokens

    @settings(max_examples=100, deadline=1000)
    @given(st.text(min_size=0, max_size=500))
    def test_determinista(self, texto: str) -> None:
        assert generar_sparse_vector(texto) == generar_sparse_vector(texto)


class TestPercentile:
    @settings(max_examples=100, deadline=1000)
    @given(st.lists(st.floats(min_value=0, max_value=1000), max_size=50), st.integers(min_value=0, max_value=100))
    def test_pct_dentro_de_rango(self, data: list[float], p: int) -> None:
        if data:
            result = percentile(data, p)
            assert min(data) <= result <= max(data)
        else:
            assert percentile(data, p) == 0.0

    @settings(max_examples=100, deadline=1000)
    @given(st.lists(st.floats(min_value=0, max_value=1000), min_size=1, max_size=50))
    def test_p0_es_minimo(self, data: list[float]) -> None:
        assert percentile(data, 0) == min(data)

    @settings(max_examples=100, deadline=1000)
    @given(st.lists(st.floats(min_value=0, max_value=1000), min_size=1, max_size=50))
    def test_p100_es_maximo(self, data: list[float]) -> None:
        assert percentile(data, 100) == max(data)


class TestChunkText:
    @settings(max_examples=100, deadline=1000)
    @given(st.text(min_size=1, max_size=1000), st.integers(min_value=1, max_value=20))
    def test_concatena_sin_perder_palabras(self, texto: str, max_words: int) -> None:
        chunks = chunk_text(texto, max_words=max_words, overlap=0)
        # Normalizar: los chunks pueden conservar whitespace original (ej: 
        # Normalizar: los chunks pueden conservar whitespace original
        unido = " ".join(" ".join(c.text.split()) for c in chunks)
        original = " ".join(texto.split())
        assert unido == original

    @settings(max_examples=100, deadline=1000)
    @given(st.text(min_size=1, max_size=1000))
    def test_primer_chunk_contiene_inicio(self, texto: str) -> None:
        chunks = chunk_text(texto, max_words=10, overlap=0)
        if chunks:
            primeras = " ".join(texto.split()[:5])
            assert primeras in chunks[0].text or len(texto.split()) <= 10

    @settings(max_examples=100, deadline=1000)
    @given(st.integers(min_value=1, max_value=100), st.integers(min_value=0, max_value=99))
    def test_overlap_menor_que_max(self, max_words: int, overlap: int) -> None:
        if overlap < max_words:
            chunks = chunk_text("x y z " * 50, max_words=max_words, overlap=overlap)
            assert len(chunks) >= 1
            for c in chunks:
                assert len(c.text.split()) <= max_words


class TestParseCoverageOutput:
    @settings(max_examples=100, deadline=1000)
    @given(st.text(max_size=2000))
    def test_nunca_crashea(self, output: str) -> None:
        result = _parse_coverage_output(output)
        assert isinstance(result, dict)

    @settings(max_examples=100, deadline=1000)
    @given(st.text(max_size=2000))
    def test_valores_porcentaje_validos(self, output: str) -> None:
        result = _parse_coverage_output(output)
        for v in result.values():
            assert 0 <= v <= 100


class TestDetectarRegresiones:
    @settings(max_examples=100, deadline=1000)
    @given(st.dictionaries(st.text(), st.dictionaries(st.text(), st.floats(allow_nan=False))))
    def test_nunca_crashea(self, reporte: dict) -> None:
        alertas = detectar_regresiones(reporte, reporte)
        assert isinstance(alertas, list)

    @settings(max_examples=100, deadline=1000)
    @given(st.text(max_size=100))
    def test_sin_reporte_siempre_alerta(self, msg: str) -> None:
        alertas = detectar_regresiones(None, {})
        assert alertas
