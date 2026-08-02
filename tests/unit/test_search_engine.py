"""Tests para core/search_engine.py."""

from unittest.mock import patch

import pytest

from core import search_engine as se


class TestSearch:
    @patch("core.search_engine.rag_enabled")
    @patch("core.search_engine.query")
    def test_rag_disabled(self, mock_query, mock_rag_enabled):
        mock_rag_enabled.return_value = False
        result = se.search("test")
        assert result == []
        mock_query.assert_not_called()

    @patch("core.search_engine.rag_enabled")
    @patch("core.search_engine.query")
    def test_query_vacia(self, mock_query, mock_rag_enabled):
        mock_rag_enabled.return_value = True
        result = se.search("")
        assert result == []
        mock_query.assert_not_called()

    @patch("core.search_engine.rag_enabled")
    @patch("core.search_engine.query")
    def test_busqueda_ok(self, mock_query, mock_rag_enabled):
        mock_rag_enabled.return_value = True
        mock_query.return_value = [{"content": "hola", "source": "doc1"}]
        result = se.search("hola", top_k=3)
        assert len(result) == 1
        assert result[0]["content"] == "hola"
        mock_query.assert_called_once_with("hola", top_k=3)

    @patch("core.search_engine.rag_enabled")
    @patch("core.search_engine.query")
    def test_busqueda_error(self, mock_query, mock_rag_enabled):
        mock_rag_enabled.return_value = True
        mock_query.side_effect = Exception("boom")
        result = se.search("hola")
        assert result == []
