"""Tests for scripts/pro/ura_query.py."""

from unittest.mock import patch

from scripts.pro.ura_query import main, run_query


class TestRunQuery:
    @patch("scripts.pro.ura_query.query")
    @patch("scripts.pro.ura_query.get_sources")
    def test_sources_only_plain(self, mock_get_sources, mock_query, capsys):
        mock_query.return_value = [{"content": "a", "source": "x", "similarity": 0.9}]
        mock_get_sources.return_value = [{"source": "x", "chunks_used": 1}]

        result = run_query("test", 3, False, True)
        captured = capsys.readouterr()

        assert result == 0
        assert "x (chunks: 1)" in captured.out
        mock_query.assert_called_once_with("test", top_k=3)
        mock_get_sources.assert_called_once()

    @patch("scripts.pro.ura_query.query")
    @patch("scripts.pro.ura_query.get_sources")
    def test_sources_only_json(self, mock_get_sources, mock_query, capsys):
        mock_query.return_value = []
        mock_get_sources.return_value = [{"source": "a", "chunks_used": 2}]

        result = run_query("test", 3, True, True)
        captured = capsys.readouterr()

        assert result == 0
        assert '"source": "a"' in captured.out
        assert '"chunks_used": 2' in captured.out

    @patch("scripts.pro.ura_query.query")
    def test_results_plain(self, mock_query, capsys):
        mock_query.return_value = [
            {"content": "hello world", "source": "doc.md", "similarity": 0.85}
        ]

        result = run_query("test", 3, False, False)
        captured = capsys.readouterr()

        assert result == 0
        assert "[0.85] doc.md:" in captured.out
        assert "hello world" in captured.out

    @patch("scripts.pro.ura_query.query")
    def test_results_json(self, mock_query, capsys):
        mock_query.return_value = [
            {"content": "hello", "source": "doc.md", "similarity": 0.85}
        ]

        result = run_query("test", 3, True, False)
        captured = capsys.readouterr()

        assert result == 0
        assert '"source": "doc.md"' in captured.out
        assert '"similarity": 0.85' in captured.out

    @patch("scripts.pro.ura_query.query")
    def test_empty_results(self, mock_query, capsys):
        mock_query.return_value = []

        result = run_query("test", 3, False, False)
        captured = capsys.readouterr()

        assert result == 0
        assert captured.out == ""


class TestMain:
    def test_no_args(self, capsys):
        result = main([])
        captured = capsys.readouterr()
        assert result == 1
        assert "URA RAG query" in captured.out

    @patch("scripts.pro.ura_query.query")
    def test_with_args(self, mock_query, capsys):
        mock_query.return_value = []
        result = main(["hello"])
        assert result == 0
