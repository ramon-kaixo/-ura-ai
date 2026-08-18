"""Tests de la migracion v15 (fix triggers FTS5 en SQLite 3.45.1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from knowledge.engine.migrations import SCHEMA_VERSION, migrate_db

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schemas" / "knowledge_graph.sql"

SCHEMA_V14 = """
CREATE TABLE IF NOT EXISTS op_assets (
    id              TEXT PRIMARY KEY,
    asset_type      TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}',
    source          TEXT NOT NULL DEFAULT '{}',
    relationships   TEXT NOT NULL DEFAULT '[]',
    quality         REAL NOT NULL DEFAULT 0.0,
    content_sha256  TEXT,
    wraps           TEXT,
    created_at      TEXT,
    updated_at      TEXT
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
CREATE TABLE IF NOT EXISTS op_memory (
    memory_id   TEXT PRIMARY KEY,
    title       TEXT,
    content     TEXT
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
"""


def _db_v14(tmp_path: Path) -> Path:
    path = tmp_path / "v14.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_V14)
    conn.execute("PRAGMA user_version = 14")
    conn.commit()
    conn.close()
    return path


def test_migracion_v15_corrige_triggers(tmp_path) -> None:
    path = _db_v14(tmp_path)
    conn = sqlite3.connect(path)
    migrate_db(conn, SCHEMA_PATH, target_version=15)
    conn.commit()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 15
    triggers = {
        r[0]: r[1] for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'")
    }
    assert "op_assets_fts_ad" in triggers
    assert "'delete'" not in triggers["op_assets_fts_ad"]
    assert "DELETE FROM op_assets_fts WHERE rowid" in triggers["op_assets_fts_ad"]
    assert "op_assets_fts_au" in triggers
    assert "'delete'" not in triggers["op_assets_fts_au"]
    conn.close()


def test_delete_funciona_tras_migracion(tmp_path) -> None:
    from knowledge.engine.asset_store import SQLiteAssetStore
    from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset

    path = _db_v14(tmp_path)
    conn = sqlite3.connect(path)
    migrate_db(conn, SCHEMA_PATH, target_version=15)
    conn.commit()
    conn.close()

    store = SQLiteAssetStore(path)
    asset = KnowledgeAsset(
        asset_id="a1",
        asset_type=AssetType.MARKDOWN,
        metadata={"title": "t", "text_preview": "b"},
        source=AssetSource(kind="web", location="", fetched_at=""),
        relationships=(),
        quality=0.5,
        created_at="",
        updated_at="",
    )
    assert store.save_asset(asset) is True
    assert store.delete_asset("a1") is True
    assert store.asset_exists("a1") is False


def test_rebuild_limpia_huerfanos(tmp_path) -> None:
    path = _db_v14(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO op_assets (id, asset_type, metadata) VALUES ('a1','md','{\"title\":\"v1\",\"text_preview\":\"c1\"}')"
    )
    conn.commit()
    conn.execute("INSERT INTO op_assets_fts(rowid, id, title, body) VALUES (99, 'huerfano', 'h', '')")
    conn.commit()
    migrate_db(conn, SCHEMA_PATH, target_version=15)
    conn.commit()
    rows = conn.execute("SELECT id FROM op_assets_fts").fetchall()
    assert [r[0] for r in rows] == ["a1"]
    conn.close()


def test_schema_version_actualizada() -> None:
    assert SCHEMA_VERSION == 15
