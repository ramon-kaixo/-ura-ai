#!/usr/bin/env python3
"""
Tests para Vocabulario Mapper
"""

import sys
from pathlib import Path

import pytest

# Agregar path al proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocabulario_mapper import VOCABULARIO_MAPPER


class TestVocabularioMapper:
    """Tests para VocabularioMapper"""

    def test_mapper_initialization(self):
        """Test inicialización del mapper"""
        assert VOCABULARIO_MAPPER is not None
        assert VOCABULARIO_MAPPER.registry is not None

    def test_find_tools_by_word(self):
        """Test buscar herramientas por palabra"""
        tools = VOCABULARIO_MAPPER.find_tools_by_word("consulta")
        assert len(tools) > 0

    def test_find_tools_by_word_no_match(self):
        """Test buscar herramientas por palabra sin coincidencia"""
        tools = VOCABULARIO_MAPPER.find_tools_by_word("palabra_inexistente_xyz")
        assert len(tools) == 0

    def test_get_vocabulario_for_tool(self):
        """Test obtener vocabulario de herramienta"""
        vocab = VOCABULARIO_MAPPER.get_vocabulario_for_tool("llm_ollama")
        assert vocab is not None
        assert "palabras_clave" in vocab or "terminos_tecnicos" in vocab

    def test_get_vocabulario_for_nonexistent_tool(self):
        """Test obtener vocabulario de herramienta inexistente"""
        vocab = VOCABULARIO_MAPPER.get_vocabulario_for_tool("nonexistent")
        assert vocab == {}

    def test_suggest_tool_for_query(self):
        """Test sugerir herramienta para consulta"""
        suggestions = VOCABULARIO_MAPPER.suggest_tool_for_query("quiero hacer una consulta")
        assert isinstance(suggestions, list)

    def test_get_synonyms(self):
        """Test obtener sinónimos"""
        synonyms = VOCABULARIO_MAPPER.get_synonyms("consulta")
        assert isinstance(synonyms, list)

    def test_get_technical_terms(self):
        """Test obtener términos técnicos"""
        terms = VOCABULARIO_MAPPER.get_technical_terms("llm")
        assert isinstance(terms, list)

    def test_get_keywords(self):
        """Test obtener palabras clave"""
        keywords = VOCABULARIO_MAPPER.get_keywords("llm")
        assert isinstance(keywords, list)

    def test_expand_query(self):
        """Test expandir consulta"""
        expanded = VOCABULARIO_MAPPER.expand_query("hacer una consulta")
        assert isinstance(expanded, list)
        assert len(expanded) >= 1

    def test_get_stats(self):
        """Test obtener estadísticas"""
        stats = VOCABULARIO_MAPPER.get_stats()

        assert "total_palabras" in stats
        assert "total_categorias" in stats
        assert "por_categoria_vocabulario" in stats

        assert stats["total_palabras"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
