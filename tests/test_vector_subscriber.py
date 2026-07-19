"""Tests for vector subscriber — MetadataExtracted → upsert pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from knowledge.engine.eventbus import MetadataExtracted
from knowledge.engine.subscribers import _make_vector_index_subscriber


@pytest.fixture
def mock_asset_store():
    """Mock SQLiteAssetStore que retorna assets ficticios."""
    with patch("knowledge.engine.asset_store.SQLiteAssetStore") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


@pytest.fixture
def embedder():
    """Mock Embedder."""
    e = MagicMock()
    e.max_input_tokens = 512
    e.embed.return_value = [[0.1, 0.2, 0.3]]
    return e


@pytest.fixture
def vector_store():
    """Mock VectorStore."""
    s = MagicMock()
    s.upsert.return_value = 1
    s.available = True
    return s


def _make_asset(
    asset_id: str = "asset-123",
    *,
    has_preview: bool = True,
    preview_text: str = "This is a test document with enough text to trigger embedding.",
    asset_type: str = "pdf",
):
    """Crea un asset mock similar a KnowledgeAsset."""
    asset = MagicMock()
    asset.asset_id = asset_id
    asset.metadata = {}
    if has_preview:
        asset.metadata["text_preview"] = preview_text
    return asset


class TestVectorIndexSubscriber:
    """Tests para el suscriptor de indexación vectorial."""

    def test_upserts_on_success(self, mock_asset_store, embedder, vector_store):
        asset = _make_asset()
        mock_asset_store.get_asset.return_value = asset
        handler = _make_vector_index_subscriber(
            "/fake/db",
            embedder,
            vector_store,
        )
        handler(
            MetadataExtracted(
                asset_id="asset-123",
                asset_type="pdf",  # type: ignore[arg-type]
                extractor="markdown",
                success=True,
                duration_ms=100.0,
            ),
        )
        embedder.embed.assert_called_once()
        vector_store.upsert.assert_called_once()
        args = vector_store.upsert.call_args[0][0]
        assert len(args) == 1
        assert args[0].asset_id == "asset-123"

    def test_skips_on_failed_extraction(self, mock_asset_store, embedder, vector_store):
        handler = _make_vector_index_subscriber(
            "/fake/db",
            embedder,
            vector_store,
        )
        handler(
            MetadataExtracted(
                asset_id="asset-123",
                asset_type="pdf",
                extractor="markdown",
                success=False,
                duration_ms=50.0,
            ),
        )
        embedder.embed.assert_not_called()
        vector_store.upsert.assert_not_called()

    def test_skips_when_no_text_preview(self, mock_asset_store, embedder, vector_store):
        asset = _make_asset(has_preview=False)
        mock_asset_store.get_asset.return_value = asset
        handler = _make_vector_index_subscriber(
            "/fake/db",
            embedder,
            vector_store,
        )
        handler(
            MetadataExtracted(
                asset_id="asset-123",
                asset_type="pdf",
                extractor="markdown",
                success=True,
                duration_ms=100.0,
            ),
        )
        embedder.embed.assert_not_called()
        vector_store.upsert.assert_not_called()

    def test_skips_when_asset_not_found(self, mock_asset_store, embedder, vector_store):
        mock_asset_store.get_asset.return_value = None
        handler = _make_vector_index_subscriber(
            "/fake/db",
            embedder,
            vector_store,
        )
        handler(
            MetadataExtracted(
                asset_id="nonexistent",
                asset_type="pdf",
                extractor="markdown",
                success=True,
                duration_ms=100.0,
            ),
        )
        embedder.embed.assert_not_called()
        vector_store.upsert.assert_not_called()

    def test_handles_embedder_unavailable(self, mock_asset_store, embedder, vector_store):
        asset = _make_asset()
        mock_asset_store.get_asset.return_value = asset
        embedder.embed.return_value = []  # embedder unavailable
        handler = _make_vector_index_subscriber(
            "/fake/db",
            embedder,
            vector_store,
        )
        handler(
            MetadataExtracted(
                asset_id="asset-123",
                asset_type="pdf",
                extractor="markdown",
                success=True,
                duration_ms=100.0,
            ),
        )
        embedder.embed.assert_called_once()
        vector_store.upsert.assert_not_called()  # no vectors → no upsert

    def test_handles_vector_store_unavailable(self, mock_asset_store, embedder, vector_store):
        asset = _make_asset()
        mock_asset_store.get_asset.return_value = asset
        vector_store.upsert.side_effect = Exception("Store down")
        handler = _make_vector_index_subscriber(
            "/fake/db",
            embedder,
            vector_store,
        )
        handler(
            MetadataExtracted(
                asset_id="asset-123",
                asset_type="pdf",
                extractor="markdown",
                success=True,
                duration_ms=100.0,
            ),
        )
        embedder.embed.assert_called_once()
        vector_store.upsert.assert_called_once()
        # No debe crashear — el handler es best-effort

    def test_truncates_by_max_input_tokens(self, mock_asset_store, embedder, vector_store):
        long_text = "A" * 2000
        asset = _make_asset(preview_text=long_text)
        mock_asset_store.get_asset.return_value = asset
        embedder.max_input_tokens = 8  # ~32 chars
        handler = _make_vector_index_subscriber(
            "/fake/db",
            embedder,
            vector_store,
        )
        handler(
            MetadataExtracted(
                asset_id="asset-123",
                asset_type="pdf",
                extractor="markdown",
                success=True,
                duration_ms=100.0,
            ),
        )
        embedder.embed.assert_called_once()
        # Verificar que se truncó
        call_text = embedder.embed.call_args[0][0][0]
        assert len(call_text) <= 32  # 8 tokens * 4 chars max

    def test_does_not_truncate_when_max_tokens_unknown(self, mock_asset_store, embedder, vector_store):
        text = "Hello world"
        asset = _make_asset(preview_text=text)
        mock_asset_store.get_asset.return_value = asset
        embedder.max_input_tokens = 0  # unknown
        handler = _make_vector_index_subscriber(
            "/fake/db",
            embedder,
            vector_store,
        )
        handler(
            MetadataExtracted(
                asset_id="asset-123",
                asset_type="pdf",
                extractor="markdown",
                success=True,
                duration_ms=100.0,
            ),
        )
        embedder.embed.assert_called_once()
        call_text = embedder.embed.call_args[0][0][0]
        assert call_text == text  # sin truncar
