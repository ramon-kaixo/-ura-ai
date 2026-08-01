"""Tests for scripts/pro/reindex_vectors.py — lógica pura con mocks."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.pro.reindex_vectors import main


class TestMain:
    @patch("scripts.pro.reindex_vectors.OllamaEmbedder")
    @patch("scripts.pro.reindex_vectors.QdrantVectorStore")
    @patch("scripts.pro.reindex_vectors.SQLiteGraphRetriever")
    @patch("scripts.pro.reindex_vectors.SQLiteAssetStore")
    @patch("scripts.pro.reindex_vectors.VectorAugmentedRetriever")
    def test_dry_run(self, mock_retriever_cls, mock_asset_cls, mock_graph_cls,
                   mock_qdrant_cls, mock_embedder_cls, caplog, tmp_path, monkeypatch):
        caplog.set_level("INFO")
        db = tmp_path / "test.db"
        db.write_text("")  # archivo vacío

        mock_retriever = MagicMock()
        mock_retriever.reconcile.return_value = {
            "to_upsert": 5, "to_delete": 2, "upserted": 0, "deleted": 0
        }
        mock_retriever_cls.return_value = mock_retriever

        monkeypatch.setattr("sys.argv", ["reindex_vectors.py", "--db", str(db)])

        main()

        assert "dry_run=True" in caplog.text
        assert "To upsert: 5" in caplog.text
        assert "To delete: 2" in caplog.text
        mock_retriever.reconcile.assert_called_once_with(dry_run=True, batch_size=100)

    @patch("scripts.pro.reindex_vectors.OllamaEmbedder")
    @patch("scripts.pro.reindex_vectors.QdrantVectorStore")
    @patch("scripts.pro.reindex_vectors.SQLiteGraphRetriever")
    @patch("scripts.pro.reindex_vectors.SQLiteAssetStore")
    @patch("scripts.pro.reindex_vectors.VectorAugmentedRetriever")
    def test_execute(self, mock_retriever_cls, mock_asset_cls, mock_graph_cls,
                     mock_qdrant_cls, mock_embedder_cls, caplog, tmp_path, monkeypatch):
        caplog.set_level("INFO")
        db = tmp_path / "test.db"
        db.write_text("")

        mock_retriever = MagicMock()
        mock_retriever.reconcile.return_value = {
            "to_upsert": 3, "to_delete": 1, "upserted": 3, "deleted": 1
        }
        mock_retriever_cls.return_value = mock_retriever

        monkeypatch.setattr("sys.argv", ["reindex_vectors.py", "--db", str(db), "--execute", "--batch", "50"])

        main()

        mock_retriever.reconcile.assert_called_once_with(dry_run=False, batch_size=50)
        assert "Upserted:  3" in caplog.text

    def test_db_not_found(self, caplog, tmp_path, monkeypatch):
        caplog.set_level("ERROR")
        db = tmp_path / "no_existe.db"

        monkeypatch.setattr("sys.argv", ["reindex_vectors.py", "--db", str(db)])

        main()

        assert "Database not found" in caplog.text

    @patch("scripts.pro.reindex_vectors.OllamaEmbedder")
    @patch("scripts.pro.reindex_vectors.QdrantVectorStore")
    @patch("scripts.pro.reindex_vectors.SQLiteGraphRetriever")
    @patch("scripts.pro.reindex_vectors.SQLiteAssetStore")
    @patch("scripts.pro.reindex_vectors.VectorAugmentedRetriever")
    def test_suggests_execute(self, mock_retriever_cls, mock_asset_cls, mock_graph_cls,
                              mock_qdrant_cls, mock_embedder_cls, caplog, tmp_path, monkeypatch):
        caplog.set_level("INFO")
        db = tmp_path / "test.db"
        db.write_text("")

        mock_retriever = MagicMock()
        mock_retriever.reconcile.return_value = {
            "to_upsert": 10, "to_delete": 0, "upserted": 0, "deleted": 0
        }
        mock_retriever_cls.return_value = mock_retriever

        monkeypatch.setattr("sys.argv", ["reindex_vectors.py", "--db", str(db)])

        main()

        assert "Usa --execute para aplicar los cambios" in caplog.text
