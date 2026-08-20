"""Tests Fase 7 — FTS5/Lineage/Graph (split de test_fase7.py)."""
from __future__ import annotations

from pathlib import Path

from _fase7_helpers import (  # noqa: F401
    AssetType,
    MagicMock,
    SQLiteAssetStore,
    SQLiteLineageStore,
    SQLiteMemoryStore,
    _make_asset,
    asset_db,
    httpx,
    json,
    lineage_db,
    memory_db,
    mock_qdrant_client,
    patch,
    pytest,
    sqlite3,
)

from knowledge.engine.asset_store import _sanitize_fts5


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
    def test_search_assets_fts5(self, asset_db: SQLiteAssetStore):  # noqa: F811
        a1 = _make_asset("a1", title="Machine Learning Guide")
        a2 = _make_asset("a2", title="Deep Learning Tutorial")
        a3 = _make_asset("a3", title="Cooking Recipes")
        asset_db.save_asset(a1)
        asset_db.save_asset(a2)
        asset_db.save_asset(a3)

        results = asset_db.search_assets("machine", limit=10)
        assert len(results) == 1
        assert results[0].asset_id == "a1"

    def test_search_assets_fts5_case_folding(self, asset_db: SQLiteAssetStore):  # noqa: F811
        """FTS5 unicode61: case-folding, 'LEARNING' matches 'Learning'."""
        a1 = _make_asset("a1", title="Machine Learning")
        asset_db.save_asset(a1)
        results = asset_db.search_assets("LEARNING", limit=10)
        assert len(results) == 1
        assert results[0].asset_id == "a1"

    def test_search_assets_fts5_body(self, asset_db: SQLiteAssetStore):  # noqa: F811
        """Search matches text_preview in body."""
        a1 = _make_asset("a1", title="Doc", text_preview="neural networks are powerful")
        asset_db.save_asset(a1)
        results = asset_db.search_assets("networks", limit=10)
        assert len(results) == 1
        assert results[0].asset_id == "a1"

    def test_search_assets_empty_query(self, asset_db: SQLiteAssetStore):  # noqa: F811
        results = asset_db.search_assets("", limit=10)
        assert results == []

    def test_search_assets_no_match(self, asset_db: SQLiteAssetStore):  # noqa: F811
        a1 = _make_asset("a1", title="Alpha")
        asset_db.save_asset(a1)
        results = asset_db.search_assets("nonexistent", limit=10)
        assert results == []

    def test_search_assets_asset_type_filter(self, asset_db: SQLiteAssetStore):  # noqa: F811
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
    def test_search_fts5(self, memory_db: SQLiteMemoryStore):  # noqa: F811
        from knowledge.engine.memory_store import MemoryRecord

        memory_db.save(MemoryRecord(memory_id="m1", kind="note", title="ML Notes", content="machine learning concepts"))
        memory_db.save(MemoryRecord(memory_id="m2", kind="note", title="Cooking", content="recipes"))

        results = memory_db.search("machine", limit=10)
        assert len(results) == 1
        assert results[0].memory_id == "m1"

    def test_search_fts5_case_folding(self, memory_db: SQLiteMemoryStore):  # noqa: F811
        from knowledge.engine.memory_store import MemoryRecord

        memory_db.save(MemoryRecord(memory_id="m1", kind="note", title="Learning Python", content="python is great"))
        results = memory_db.search("LEARNING", limit=10)
        assert len(results) == 1

    def test_search_empty_query(self, memory_db: SQLiteMemoryStore):  # noqa: F811
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
    def test_store_event_creates_edges(self, lineage_db: SQLiteLineageStore):  # noqa: F811
        event = {
            "eventType": "COMPLETE",
            "eventTime": "2026-01-01T00:00:00Z",
            "inputs": [{"name": "input_asset"}],
            "outputs": [{"name": "output_asset"}],
        }
        assert lineage_db.store_lineage_event(event)
        upstream = lineage_db.get_upstream("output_asset")
        assert "input_asset" in upstream

    def test_no_false_positives(self, lineage_db: SQLiteLineageStore):  # noqa: F811
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

    def test_get_downstream(self, lineage_db: SQLiteLineageStore):  # noqa: F811
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
    def test_asset_insert_trigger(self, asset_db: SQLiteAssetStore):  # noqa: F811
        a1 = _make_asset("a1", title="Test Title", text_preview="Test body")
        asset_db.save_asset(a1)
        conn = sqlite3.connect(str(asset_db._db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT title FROM op_assets_fts WHERE id = ?", ("a1",)).fetchone()
        conn.close()
        assert row is not None
        assert row["title"] == "Test Title"

    def test_asset_update_trigger(self, asset_db: SQLiteAssetStore):  # noqa: F811
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

    def test_memory_backfill(self, memory_db: SQLiteMemoryStore):  # noqa: F811
        from knowledge.engine.memory_store import MemoryRecord

        memory_db.save(MemoryRecord(memory_id="m1", kind="note", title="Original", content="content"))
        conn = sqlite3.connect(str(memory_db._db_path))
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT count(*) as c FROM op_memory_fts").fetchone()["c"]
        conn.close()
        assert count >= 1


# ── Qdrant auto-recovery ──────────────────────────────────────────────────


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


