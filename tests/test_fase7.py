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

from knowledge.engine.asset_store import SQLiteAssetStore, _sanitize_fts5
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


class TestSanitizeFts5:
    def test_simple_query(self):
        assert _sanitize_fts5("machine learning") == '"machine" "learning"'

    def test_single_term(self):
        assert _sanitize_fts5("hello") == '"hello"'

    def test_escapes_double_quotes(self):
        assert _sanitize_fts5('say "hello"') == '"say" """hello"""'

    def test_empty_returns_empty(self):
        assert _sanitize_fts5("") == ""

    def test_whitespace_only_returns_empty(self):
        assert _sanitize_fts5("   ") == ""


# ── AssetStore.search_assets ──────────────────────────────────────────────


class TestAssetStoreSearchFts5:
    def test_search_assets_fts5(self, asset_db: SQLiteAssetStore):
        a1 = _make_asset("a1", title="Machine Learning Guide")
        a2 = _make_asset("a2", title="Deep Learning Tutorial")
        a3 = _make_asset("a3", title="Cooking Recipes")
        asset_db.save_asset(a1)
        asset_db.save_asset(a2)
        asset_db.save_asset(a3)

        results = asset_db.search_assets("machine", limit=10)
        assert len(results) == 1
        assert results[0].asset_id == "a1"

    def test_search_assets_fts5_case_folding(self, asset_db: SQLiteAssetStore):
        """FTS5 unicode61: case-folding, 'LEARNING' matches 'Learning'."""
        a1 = _make_asset("a1", title="Machine Learning")
        asset_db.save_asset(a1)
        results = asset_db.search_assets("LEARNING", limit=10)
        assert len(results) == 1
        assert results[0].asset_id == "a1"

    def test_search_assets_fts5_body(self, asset_db: SQLiteAssetStore):
        """Search matches text_preview in body."""
        a1 = _make_asset("a1", title="Doc", text_preview="neural networks are powerful")
        asset_db.save_asset(a1)
        results = asset_db.search_assets("networks", limit=10)
        assert len(results) == 1
        assert results[0].asset_id == "a1"

    def test_search_assets_empty_query(self, asset_db: SQLiteAssetStore):
        results = asset_db.search_assets("", limit=10)
        assert results == []

    def test_search_assets_no_match(self, asset_db: SQLiteAssetStore):
        a1 = _make_asset("a1", title="Alpha")
        asset_db.save_asset(a1)
        results = asset_db.search_assets("nonexistent", limit=10)
        assert results == []

    def test_search_assets_asset_type_filter(self, asset_db: SQLiteAssetStore):
        a1 = _make_asset("a1", title="Machine Learning")
        asset_db.save_asset(a1)
        results = asset_db.search_assets("machine", limit=10, asset_type=AssetType("image"))
        assert results == []

    def test_search_assets_fallback_like(self, tmp_path: Path):
        """Sin FTS5, el fallback LIKE funciona."""
        db = tmp_path / "test_nofts.db"
        store = SQLiteAssetStore(db)
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_assets (
                id TEXT PRIMARY KEY, asset_type TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL DEFAULT '{}',
                relationships TEXT NOT NULL DEFAULT '[]', quality REAL NOT NULL DEFAULT 0.0,
                content_sha256 TEXT, wraps TEXT, created_at TEXT, updated_at TEXT
            );
        """)
        conn.commit()
        conn.close()
        a1 = _make_asset("a1", title="Machine Learning")
        store.save_asset(a1)
        results = store.search_assets("machine", limit=10)
        assert len(results) >= 1


# ── MemoryStore.search ────────────────────────────────────────────────────


class TestMemoryStoreSearchFts5:
    def test_search_fts5(self, memory_db: SQLiteMemoryStore):
        from knowledge.engine.memory_store import MemoryRecord

        memory_db.save(MemoryRecord(memory_id="m1", kind="note", title="ML Notes", content="machine learning concepts"))
        memory_db.save(MemoryRecord(memory_id="m2", kind="note", title="Cooking", content="recipes"))

        results = memory_db.search("machine", limit=10)
        assert len(results) == 1
        assert results[0].memory_id == "m1"

    def test_search_fts5_case_folding(self, memory_db: SQLiteMemoryStore):
        from knowledge.engine.memory_store import MemoryRecord

        memory_db.save(MemoryRecord(memory_id="m1", kind="note", title="Learning Python", content="python is great"))
        results = memory_db.search("LEARNING", limit=10)
        assert len(results) == 1

    def test_search_empty_query(self, memory_db: SQLiteMemoryStore):
        results = memory_db.search("", limit=10)
        assert results == []

    def test_search_fallback_like(self, tmp_path: Path):
        """Sin FTS5, fallback LIKE funciona."""
        from knowledge.engine.memory_store import MemoryRecord, SQLiteMemoryStore

        db = tmp_path / "test_nofts_mem.db"
        store = SQLiteMemoryStore(db)
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_memory (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
                title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
                related_assets TEXT NOT NULL DEFAULT '[]', tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT, updated_at TEXT
            );
        """)
        conn.commit()
        conn.close()
        store.save(MemoryRecord(memory_id="m1", kind="note", title="ML Notes", content="machine learning"))
        results = store.search("machine", limit=10)
        assert len(results) == 1


# ── LineageStore edges ────────────────────────────────────────────────────


class TestLineageEdges:
    def test_store_event_creates_edges(self, lineage_db: SQLiteLineageStore):
        event = {
            "eventType": "COMPLETE",
            "eventTime": "2026-01-01T00:00:00Z",
            "inputs": [{"name": "input_asset"}],
            "outputs": [{"name": "output_asset"}],
        }
        assert lineage_db.store_lineage_event(event)
        upstream = lineage_db.get_upstream("output_asset")
        assert "input_asset" in upstream

    def test_no_false_positives(self, lineage_db: SQLiteLineageStore):
        """'abc' no debe matchear 'abc123'."""
        event = {
            "eventType": "COMPLETE",
            "eventTime": "2026-01-01T00:00:00Z",
            "inputs": [{"name": "abc"}],
            "outputs": [{"name": "xyz"}],
        }
        lineage_db.store_lineage_event(event)
        upstream = lineage_db.get_upstream("xyz")
        assert "abc" in upstream
        assert "abc123" not in upstream

    def test_get_downstream(self, lineage_db: SQLiteLineageStore):
        event = {
            "eventType": "COMPLETE",
            "eventTime": "2026-01-01T00:00:00Z",
            "inputs": [{"name": "src"}],
            "outputs": [{"name": "dst1"}, {"name": "dst2"}],
        }
        lineage_db.store_lineage_event(event)
        downstream = lineage_db.get_downstream("src")
        assert "dst1" in downstream
        assert "dst2" in downstream

    def test_graceful_when_edges_table_missing(self, tmp_path: Path):
        """Sin op_lineage_edges, debe caer en LIKE."""
        db = tmp_path / "test_noedges.db"
        store = SQLiteLineageStore(db)
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_lineage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL, event_time TEXT NOT NULL,
                run_id TEXT, job_name TEXT, namespace TEXT,
                input_ids TEXT NOT NULL DEFAULT '[]',
                output_ids TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            );
        """)
        conn.commit()
        conn.close()
        event = {
            "eventType": "COMPLETE",
            "eventTime": "2026-01-01T00:00:00Z",
            "inputs": [{"name": "input_asset"}],
            "outputs": [{"name": "output_asset"}],
        }
        assert store.store_lineage_event(event)
        upstream = store.get_upstream("output_asset")
        assert "input_asset" in upstream


# ── FTS5 Triggers ─────────────────────────────────────────────────────────


class TestFts5Triggers:
    def test_asset_insert_trigger(self, asset_db: SQLiteAssetStore):
        a1 = _make_asset("a1", title="Test Title", text_preview="Test body")
        asset_db.save_asset(a1)
        conn = sqlite3.connect(str(asset_db._db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT title FROM op_assets_fts WHERE id = ?", ("a1",)).fetchone()
        conn.close()
        assert row is not None
        assert row["title"] == "Test Title"

    def test_asset_update_trigger(self, asset_db: SQLiteAssetStore):
        """After INSERT trigger puebla op_assets_fts."""
        a1 = _make_asset("a1", title="Test Title", text_preview="Test body")
        asset_db.save_asset(a1)
        conn = sqlite3.connect(str(asset_db._db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT title, body FROM op_assets_fts WHERE id = ?", ("a1",)).fetchone()
        conn.close()
        assert row is not None
        assert row["title"] == "Test Title"
        assert row["body"] == "Test body"

    def test_memory_backfill(self, memory_db: SQLiteMemoryStore):
        from knowledge.engine.memory_store import MemoryRecord

        memory_db.save(MemoryRecord(memory_id="m1", kind="note", title="Original", content="content"))
        conn = sqlite3.connect(str(memory_db._db_path))
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT count(*) as c FROM op_memory_fts").fetchone()["c"]
        conn.close()
        assert count >= 1


# ── Qdrant auto-recovery ──────────────────────────────────────────────────


@pytest.fixture
def mock_qdrant_client():
    with patch("knowledge.engine.vector_qdrant.httpx.Client") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


class TestQdrantAutoRecovery:
    def test_check_available_resets_degraded(self, mock_qdrant_client):
        store = QdrantVectorStore(collection="test")
        store._degraded = True
        store._last_check = 0.0
        mock_qdrant_client.get.return_value.status_code = 200
        assert store.check_available()
        assert store.available

    def test_check_available_4xx_no_recovery(self, mock_qdrant_client):
        store = QdrantVectorStore(collection="test")
        store._degraded = True
        store._last_check = 0.0
        resp = MagicMock()
        resp.status_code = 403
        mock_qdrant_client.get.return_value = resp
        assert not store.check_available()
        assert not store.available

    def test_check_available_5xx_backoff(self, mock_qdrant_client):
        store = QdrantVectorStore(collection="test")
        store._degraded = True
        store._last_check = 0.0
        mock_qdrant_client.get.side_effect = httpx.HTTPError("5xx")
        assert not store.check_available()
        assert store._backoff > 1.0

    def test_available_returns_not_degraded(self, mock_qdrant_client):
        store = QdrantVectorStore(collection="test")
        assert store.available
        store._degraded = True
        assert not store.available


# ── Ollama auto-recovery ─────────────────────────────────────────────────


@pytest.fixture
def mock_ollama_health():
    with patch("knowledge.engine.vector_ollama._health") as m:
        yield m


class TestOllamaAutoRecovery:
    def test_check_available_resets_degraded(self, mock_ollama_health):
        embedder = OllamaEmbedder()
        embedder._degraded = True
        embedder._last_check = 0.0
        mock_ollama_health.return_value = {"status": "ok", "modelos_disponibles": [], "latency_ms": 5}
        assert embedder.check_available()
        assert embedder.available

    def test_check_available_failure_backoff(self, mock_ollama_health):
        embedder = OllamaEmbedder()
        embedder._degraded = True
        embedder._last_check = 0.0
        mock_ollama_health.return_value = {"status": "error", "detail": "fail", "latency_ms": 100}
        assert not embedder.check_available()
        assert embedder._backoff > 1.0

    def test_available_returns_boolean(self, mock_ollama_health):
        embedder = OllamaEmbedder()
        assert embedder.available
        embedder._degraded = True
        assert not embedder.available


# ── ExtractionService queue ───────────────────────────────────────────────


class TestExtractionQueue:
    def test_queue_extract_creates_job(self, tmp_path: Path):
        from knowledge.engine.extraction_service import MetadataExtractionService

        db = tmp_path / "test_queue.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL, priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', payload TEXT, dedup_key TEXT,
                created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                error TEXT, result_data TEXT
            );
        """)
        conn.commit()
        conn.close()

        service = MetadataExtractionService(db)
        job_id = service.queue_extract(AssetSource("filesystem", "/tmp/test.md"))  # noqa: S108

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status, job_type FROM op_jobs WHERE id = ?", (int(job_id),)).fetchone()
        conn.close()
        assert row is not None
        assert row["status"] == "pending"
        assert row["job_type"] == "extraction"

    def test_get_queue_status(self, tmp_path: Path):
        from knowledge.engine.extraction_service import MetadataExtractionService

        db = tmp_path / "test_status.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL, priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', payload TEXT, dedup_key TEXT,
                created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                error TEXT, result_data TEXT
            );
        """)
        cur = conn.execute(
            "INSERT INTO op_jobs (job_type, status, created_at) VALUES ('extraction', 'done', datetime('now'))",
        )
        job_id = str(cur.lastrowid)
        conn.commit()
        conn.close()

        service = MetadataExtractionService(db)
        status = service.get_queue_status(job_id)
        assert status["status"] == "done"

    def test_get_queue_status_not_found(self, tmp_path: Path):
        from knowledge.engine.extraction_service import MetadataExtractionService

        db = tmp_path / "test_nf.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL, priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', payload TEXT, dedup_key TEXT,
                created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                error TEXT, result_data TEXT
            );
        """)
        conn.commit()
        conn.close()

        service = MetadataExtractionService(db)
        status = service.get_queue_status("9999")
        assert status["status"] == "not_found"


# ── Reconciliation ────────────────────────────────────────────────────────


class TestReconcile:
    def test_reconcile_dry_run_no_changes(self):
        """Dry-run no modifica nada."""
        graph = MagicMock()
        asset_store = MagicMock()
        embedder = MagicMock()
        vector_store = MagicMock()

        asset_store.list_assets.return_value = []
        vector_store.list_ids.return_value = ([], None)

        retriever = VectorAugmentedRetriever(graph, asset_store, embedder, vector_store)
        stats = retriever.reconcile(dry_run=True)

        assert stats["to_upsert"] == 0
        assert stats["to_delete"] == 0
        assert stats["upserted"] == 0
        assert stats["deleted"] == 0

    def test_reconcile_dry_run_reports_pending(self):
        """Dry-run reporta assets sin indexar sin modificarlos."""
        graph = MagicMock()
        asset_store = MagicMock()
        embedder = MagicMock()
        vector_store = MagicMock()

        a1 = _make_asset("a1", title="Test Asset")
        asset_store.list_assets.side_effect = [[a1], []]  # first batch, then empty
        vector_store.list_ids.return_value = ([], None)  # store vacío
        embedder.vector_size = 384
        embedder.embed.return_value = [[0.1] * 384]

        retriever = VectorAugmentedRetriever(graph, asset_store, embedder, vector_store)
        stats = retriever.reconcile(dry_run=True)

        assert stats["to_upsert"] >= 1
        assert stats["upserted"] == 0


# ── list_ids + _get_vector_ids (H1 fix) ──────────────────────────────────


class TestListIds:
    """Verifica que list_ids() y _get_vector_ids() no tienen loop infinito."""

    def test_qdrant_list_ids_calls_scroll_endpoint(self, mock_qdrant_client):
        """list_ids() llama a scroll API de Qdrant con los parámetros correctos."""
        store = QdrantVectorStore(collection="test")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "points": [{"id": "a1"}, {"id": "a2"}],
                "next_page_offset": None,
            },
        }
        mock_qdrant_client.post.return_value = mock_response

        ids, next_offset = store.list_ids(limit=50)

        assert ids == ["a1", "a2"]
        assert next_offset is None
        # Verifica que llamó a scroll, no a search
        call_args = mock_qdrant_client.post.call_args
        assert "/scroll" in call_args[0][0]
        assert call_args[1]["json"]["limit"] == 50
        assert "with_payload" in call_args[1]["json"]

    def test_qdrant_list_ids_pagination(self, mock_qdrant_client):
        """list_ids() pasa offset a Qdrant en páginas siguientes."""
        store = QdrantVectorStore(collection="test")

        def side_effect(*args, **kwargs):
            body = kwargs.get("json", {})
            offset = body.get("offset")
            resp = MagicMock()
            if offset is None:
                resp.json.return_value = {
                    "result": {
                        "points": [{"id": f"page1_{i}"} for i in range(3)],
                        "next_page_offset": "cursor_abc",
                    },
                }
            else:
                resp.json.return_value = {
                    "result": {
                        "points": [{"id": f"page2_{i}"} for i in range(2)],
                        "next_page_offset": None,
                    },
                }
            return resp

        mock_qdrant_client.post.side_effect = side_effect

        # Primera página
        ids1, next1 = store.list_ids(limit=3)
        assert len(ids1) == 3
        assert next1 == "cursor_abc"

        # Segunda página
        ids2, next2 = store.list_ids(limit=3, offset=next1)
        assert len(ids2) == 2
        assert next2 is None

    def test_qdrant_list_ids_degraded(self, mock_qdrant_client):
        """list_ids() retorna vacío si el store está degradado."""
        store = QdrantVectorStore(collection="test")
        store._degraded = True
        ids, next_offset = store.list_ids()
        assert ids == []
        assert next_offset is None

    def test_get_vector_ids_no_infinite_loop(self):
        """_get_vector_ids() termina con >100 vectores (sin loop infinito)."""
        graph = MagicMock()
        asset_store = MagicMock()
        embedder = MagicMock()
        embedder.vector_size = 384
        vector_store = MagicMock()

        # Simula 250 vectores en 3 páginas (100 + 100 + 50)
        calls = 0

        def mock_list_ids(limit=100, offset=None):
            nonlocal calls
            calls += 1
            if offset is None:
                ids = [f"asset_{i}" for i in range(100)]
                return ids, "cursor_1"
            if offset == "cursor_1":
                ids = [f"asset_{i}" for i in range(100, 200)]
                return ids, "cursor_2"
            ids = [f"asset_{i}" for i in range(200, 250)]
            return ids, None

        vector_store.list_ids.side_effect = mock_list_ids
        retriever = VectorAugmentedRetriever(
            graph,
            asset_store,
            embedder,
            vector_store,
        )
        result = retriever._get_vector_ids()

        assert len(result) == 250
        assert calls == 3
        assert "asset_0" in result
        assert "asset_249" in result

    def test_get_vector_ids_duplicate_offset(self, caplog):
        """_get_vector_ids() rompe el loop si next_offset se repite (M04)."""
        graph = MagicMock()
        asset_store = MagicMock()
        embedder = MagicMock()
        embedder.vector_size = 384
        vector_store = MagicMock()

        calls = 0

        def mock_list_ids(limit=100, offset=None):
            nonlocal calls
            calls += 1
            ids = [f"asset_{calls * 100 + i}" for i in range(100)]
            return ids, "cursor_stuck"

        vector_store.list_ids.side_effect = mock_list_ids
        retriever = VectorAugmentedRetriever(
            graph,
            asset_store,
            embedder,
            vector_store,
        )

        with caplog.at_level("WARNING"):
            result = retriever._get_vector_ids()

        assert len(result) == 200
        assert calls == 2
        assert "Duplicate next_offset=cursor_stuck" in caplog.text

    def test_get_vector_ids_empty(self):
        """_get_vector_ids() con store vacío retorna set vacío."""
        graph = MagicMock()
        asset_store = MagicMock()
        embedder = MagicMock()
        vector_store = MagicMock()
        vector_store.list_ids.return_value = ([], None)

        retriever = VectorAugmentedRetriever(
            graph,
            asset_store,
            embedder,
            vector_store,
        )
        result = retriever._get_vector_ids()
        assert result == set()

    def test_get_vector_ids_degraded(self):
        """_get_vector_ids() con store degradado retorna set vacío."""
        graph = MagicMock()
        asset_store = MagicMock()
        embedder = MagicMock()
        vector_store = MagicMock()
        vector_store.list_ids.side_effect = Exception("degraded")

        retriever = VectorAugmentedRetriever(
            graph,
            asset_store,
            embedder,
            vector_store,
        )
        result = retriever._get_vector_ids()
        assert result == set()

    def test_reconcile_with_many_vectors_completes(self):
        """reconcile() con >100 vectores en store no hace loop infinito."""
        graph = MagicMock()
        asset_store = MagicMock()
        embedder = MagicMock()
        embedder.vector_size = 384
        vector_store = MagicMock()

        # 250 assets en AssetStore
        many_assets = [_make_asset(f"a{i}", title=f"Asset {i}") for i in range(250)]
        # list_assets devuelve en batches de 100
        asset_store.list_assets.side_effect = [
            many_assets[0:100],
            many_assets[100:200],
            many_assets[200:250],
            [],
        ]
        embedder.embed.return_value = [[0.1] * 384]

        # list_ids devuelve que NO hay vectores (store vacío)
        vector_store.list_ids.return_value = ([], None)

        retriever = VectorAugmentedRetriever(
            graph,
            asset_store,
            embedder,
            vector_store,
        )
        stats = retriever.reconcile(dry_run=True)

        assert stats["to_upsert"] == 250
        assert stats["to_delete"] == 0
        assert stats["upserted"] == 0
        assert stats["deleted"] == 0

    def test_reconcile_with_matching_vectors(self):
        """reconcile() detecta correctamente assets ya indexados."""
        graph = MagicMock()
        asset_store = MagicMock()
        embedder = MagicMock()
        embedder.vector_size = 384
        vector_store = MagicMock()

        # 50 assets, 30 ya indexados, 20 pendientes
        assets = [_make_asset(f"a{i}", title=f"A{i}") for i in range(50)]
        asset_store.list_assets.side_effect = [assets, []]

        indexed_ids = {f"a{i}" for i in range(30)}

        def mock_list_ids(limit=100, offset=None):
            return list(indexed_ids), None

        vector_store.list_ids.side_effect = mock_list_ids
        embedder.embed.return_value = [[0.1] * 384]

        retriever = VectorAugmentedRetriever(
            graph,
            asset_store,
            embedder,
            vector_store,
        )
        stats = retriever.reconcile(dry_run=True)

        assert stats["to_upsert"] == 20  # 50 - 30 = 20 pendientes
        assert stats["to_delete"] == 0


# ── GraphRetriever integration ────────────────────────────────────────────


class TestGraphRetrieverFts5:
    def test_retrieve_assets_uses_search_assets(self, tmp_path: Path):
        """Verifica que retrieve_assets llama a search_assets."""
        from knowledge.engine.graphrag import SQLiteGraphRetriever

        db = tmp_path / "test_graph.db"
        # Usar dos conexiones separadas para evitar database is locked
        conn1 = sqlite3.connect(str(db))
        conn1.row_factory = sqlite3.Row
        conn1.execute("PRAGMA journal_mode=WAL")
        conn1.executescript("""
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
        """)
        conn1.commit()
        meta = json.dumps({"title": "Machine Learning Guide"})
        conn1.execute(
            "INSERT INTO op_assets (id, asset_type, metadata, source, quality, created_at, updated_at) "
            "VALUES ('a1', 'pdf', ?, '{}', 1.0, datetime('now'), datetime('now'))",
            (meta,),
        )
        conn1.commit()
        conn1.close()

        retriever = SQLiteGraphRetriever(db)
        results = retriever.retrieve_assets("machine", limit=10)
        assert len(results) == 1
        assert results[0].asset_id == "a1"


# ── Integration tests ─────────────────────────────────────────────────────


class TestIntegration:
    """Tests de integración de Fase 7.

    Requieren: SQLite con FTS5, EventBus.
    Opcionales: Ollama, Qdrant.
    """

    def test_e2e_fts5_search(self, tmp_path: Path):
        """Pipeline completo: save_asset → search_assets retorna asset."""
        from knowledge.engine.graphrag import SQLiteGraphRetriever

        db = tmp_path / "e2e_fts5.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            PRAGMA journal_mode=WAL;
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
        """)
        conn.commit()

        asset = _make_asset("e2e1", title="End to End Test", text_preview="integration testing")
        store = SQLiteAssetStore(db)
        store.save_asset(asset)

        retriever = SQLiteGraphRetriever(db)
        results = retriever.retrieve_assets("integration", limit=5)
        assert len(results) >= 1
        assert results[0].asset_id == "e2e1"

        # También desde search_assets directo
        direct = store.search_assets("end to end", limit=5)
        assert len(direct) >= 1
        conn.close()

    def test_e2e_lineage_edges(self, tmp_path: Path):
        """Lineage event → edges consultable sin LIKE."""
        db = tmp_path / "e2e_lineage.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            PRAGMA journal_mode=WAL;
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

        store = SQLiteLineageStore(db)
        event = {
            "eventType": "COMPLETE",
            "eventTime": "2026-06-01T00:00:00Z",
            "inputs": [{"name": "input_a"}, {"name": "input_b"}],
            "outputs": [{"name": "output_x"}],
        }
        assert store.store_lineage_event(event)

        upstream = store.get_upstream("output_x")
        assert "input_a" in upstream
        assert "input_b" in upstream
        assert "input_c" not in upstream

    def test_e2e_degraded_fallback(self, tmp_path: Path):
        """Sin FTS5 ni edges, todo funciona con LIKE."""
        db = tmp_path / "e2e_degraded.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS op_assets (
                id TEXT PRIMARY KEY, asset_type TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL DEFAULT '{}',
                relationships TEXT NOT NULL DEFAULT '[]', quality REAL NOT NULL DEFAULT 0.0,
                content_sha256 TEXT, wraps TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS op_lineage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL, event_time TEXT NOT NULL,
                run_id TEXT, job_name TEXT, namespace TEXT,
                input_ids TEXT NOT NULL DEFAULT '[]',
                output_ids TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            );
        """)
        conn.commit()

        meta = json.dumps({"title": "Degraded Test"})
        conn.execute(
            "INSERT INTO op_assets (id, asset_type, metadata, quality, created_at, updated_at) "
            "VALUES ('d1', 'pdf', ?, 1.0, datetime('now'), datetime('now'))",
            (meta,),
        )
        conn.execute(
            "INSERT INTO op_lineage (event_type, event_time, input_ids, output_ids) "
            "VALUES ('COMPLETE', datetime('now'), '[\"src\"]', '[\"d1\"]')",
        )
        conn.commit()
        conn.close()

        from knowledge.engine.graphrag import SQLiteGraphRetriever

        store = SQLiteAssetStore(db)
        lineage = SQLiteLineageStore(db)
        retriever = SQLiteGraphRetriever(db)

        # Sin FTS5 → fallback LIKE
        results = store.search_assets("degraded", limit=5)
        assert len(results) >= 1
        assert results[0].asset_id == "d1"

        # Sin edges → fallback LIKE
        up = lineage.get_upstream("d1")
        assert "src" in up

        # GraphRetriever igualmente funciona
        r = retriever.retrieve_assets("degraded", limit=5)
        assert len(r) >= 1
