"""Tests para Fase 7 — Optimizaciones de Producción.

Cubre: AssetStore.search_assets, MemoryStore.search (FTS5), LineageStore edges,
ExtractionService queue, VectorStore/Embedder auto-recovery, reconcile.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import httpx
import pytest

from knowledge.engine.asset_store import SQLiteAssetStore
from knowledge.engine.lineage_store import SQLiteLineageStore
from knowledge.engine.memory_store import SQLiteMemoryStore
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset
from knowledge.engine.vector_ollama import OllamaEmbedder
from knowledge.engine.vector_qdrant import QdrantVectorStore
from knowledge.engine.vector_retriever import VectorAugmentedRetriever

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_asset(asset_id: str, title: str = "", text_preview: str = "") -> KnowledgeAsset:
    return KnowledgeAsset(
        asset_id=asset_id,
        asset_type=AssetType("pdf"),
        metadata={"title": title, "text_preview": text_preview} if title else {},
        source=AssetSource(kind="test", location=""),
        quality=1.0,
    )


@pytest.fixture
def asset_db(tmp_path: Path) -> Generator[SQLiteAssetStore, None, None]:
    """Crea BD con op_assets + op_assets_fts para tests de búsqueda."""
    db = tmp_path / "test_assets.db"
    store = SQLiteAssetStore(db)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS op_assets (
            id TEXT PRIMARY KEY, asset_type TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL DEFAULT '{}',
            relationships TEXT NOT NULL DEFAULT '[]', quality REAL NOT NULL DEFAULT 0.0,
            content_sha256 TEXT, wraps TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS op_assets_fts USING fts5(
            id UNINDEXED, title, body, tokenize = 'unicode61'
        );
        CREATE TRIGGER IF NOT EXISTS op_assets_fts_ai AFTER INSERT ON op_assets BEGIN
            INSERT INTO op_assets_fts(rowid, id, title, body)
            VALUES (new.rowid, new.id,
                    json_extract(new.metadata, '$.title'),
                    COALESCE(json_extract(new.metadata, '$.text_preview'), ''));
        END;
        CREATE TRIGGER IF NOT EXISTS op_assets_fts_ad AFTER DELETE ON op_assets BEGIN
            INSERT INTO op_assets_fts(op_assets_fts, rowid, id, title, body)
            VALUES ('delete', old.rowid, old.id, '', '');
        END;
        CREATE TRIGGER IF NOT EXISTS op_assets_fts_au AFTER UPDATE ON op_assets BEGIN
            INSERT INTO op_assets_fts(op_assets_fts, rowid, id, title, body)
            VALUES ('delete', old.rowid, old.id, '', '');
            INSERT INTO op_assets_fts(rowid, id, title, body)
            VALUES (new.rowid, new.id,
                    json_extract(new.metadata, '$.title'),
                    COALESCE(json_extract(new.metadata, '$.text_preview'), ''));
        END;
    """)
    conn.commit()
    conn.close()
    return store


@pytest.fixture
def memory_db(tmp_path: Path) -> Generator[SQLiteMemoryStore, None, None]:
    """Crea BD con op_memory + op_memory_fts para tests de búsqueda."""
    db = tmp_path / "test_memory.db"
    store = SQLiteMemoryStore(db)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS op_memory (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
            title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
            related_assets TEXT NOT NULL DEFAULT '[]', tags TEXT NOT NULL DEFAULT '[]',
            metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT, updated_at TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS op_memory_fts USING fts5(
            id UNINDEXED, title, content, tokenize = 'unicode61'
        );
        CREATE TRIGGER IF NOT EXISTS op_memory_fts_ai AFTER INSERT ON op_memory BEGIN
            INSERT INTO op_memory_fts(rowid, id, title, content)
            VALUES (new.rowid, new.memory_id, new.title, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS op_memory_fts_ad AFTER DELETE ON op_memory BEGIN
            INSERT INTO op_memory_fts(op_memory_fts, rowid, id, title, content)
            VALUES ('delete', old.rowid, old.memory_id, '', '');
        END;
        CREATE TRIGGER IF NOT EXISTS op_memory_fts_au AFTER UPDATE ON op_memory BEGIN
            INSERT INTO op_memory_fts(op_memory_fts, rowid, id, title, content)
            VALUES ('delete', old.rowid, old.memory_id, '', '');
            INSERT INTO op_memory_fts(rowid, id, title, content)
            VALUES (new.rowid, new.memory_id, new.title, new.content);
        END;
    """)
    conn.commit()
    conn.close()
    return store


@pytest.fixture
def lineage_db(tmp_path: Path) -> Generator[SQLiteLineageStore, None, None]:
    """Crea BD con op_lineage + op_lineage_edges."""
    db = tmp_path / "test_lineage.db"
    store = SQLiteLineageStore(db)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS op_lineage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL, event_time TEXT NOT NULL,
            run_id TEXT, job_name TEXT, namespace TEXT,
            input_ids TEXT NOT NULL DEFAULT '[]',
            output_ids TEXT NOT NULL DEFAULT '[]',
            metadata TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS op_lineage_edges (
            src TEXT NOT NULL, dst TEXT NOT NULL,
            relation TEXT NOT NULL, event_id INTEGER REFERENCES op_lineage(id),
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_src ON op_lineage_edges(src);
        CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_dst ON op_lineage_edges(dst);
    """)
    conn.commit()
    conn.close()
    return store


# ── _sanitize_fts5 ─────────────────────────────────────────────────────────




@pytest.fixture
def mock_qdrant_client():
    with patch("knowledge.engine.vector_qdrant.httpx.Client") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


@pytest.fixture
def mock_ollama_health():
    with patch("knowledge.engine.vector_ollama._health") as m:
        yield m
