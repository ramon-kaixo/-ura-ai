"""Tests de cobertura de knowledge/engine/asset_store.py (SQLiteAssetStore)."""

from __future__ import annotations

import sqlite3

from knowledge.engine.asset_store import SQLiteAssetStore, _sanitize_fts5
from knowledge.engine.ontology.internal import (
    AssetRelationship,
    AssetSource,
    AssetType,
    KnowledgeAsset,
)

SCHEMA = """
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
    DELETE FROM op_assets_fts WHERE rowid = old.rowid;
END;
CREATE TRIGGER IF NOT EXISTS op_assets_fts_au AFTER UPDATE ON op_assets BEGIN
    DELETE FROM op_assets_fts WHERE rowid = old.rowid;
    INSERT INTO op_assets_fts(rowid, id, title, body)
    VALUES (new.rowid, new.id,
            json_extract(new.metadata, '$.title'),
            COALESCE(json_extract(new.metadata, '$.text_preview'), ''));
END;
"""


def _db(tmp_path, name: str = "ke.db"):
    path = tmp_path / name
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return path


def _asset(asset_id: str = "a1", title: str = "Titulo Prueba", asset_type: AssetType = AssetType.MARKDOWN) -> KnowledgeAsset:
    return KnowledgeAsset(
        asset_id=asset_id,
        asset_type=asset_type,
        metadata={"title": title, "text_preview": "cuerpo de prueba"},
        source=AssetSource(kind="web", location="https://x.com", fetched_at="2026-08-18"),
        relationships=(
            AssetRelationship(target_id="a2", relation="cites", metadata={"k": 1}),
        ),
        quality=0.9,
        created_at="2026-08-18T00:00:00",
        updated_at="2026-08-18T00:00:00",
    )


class TestSave:
    def test_guarda_y_actualiza(self, tmp_path) -> None:
        store = SQLiteAssetStore(_db(tmp_path))
        assert store.save_asset(_asset()) is True
        assert store.asset_exists("a1") is True
        import dataclasses

        up = dataclasses.replace(_asset(), metadata={"title": "Nuevo", "text_preview": "v2"})
        assert store.save_asset(up) is True
        assert store.get_asset("a1").metadata["title"] == "Nuevo"

    def test_error_db_cerrada(self, tmp_path) -> None:
        store = SQLiteAssetStore(_db(tmp_path))
        store.get_asset("x")  # abre/cierra bien
        path = store._db_path
        conn = sqlite3.connect(path)
        conn.close()  # deja un lock del fichero abierto? no: cerrada -> siguiente open_db OK.
        # Forzamos error: sqlite3.connect sobre un directorio
        store = SQLiteAssetStore(tmp_path / "no-es-db")
        assert store.save_asset(_asset()) is False


class TestGet:
    def test_ok(self, tmp_path) -> None:
        store = SQLiteAssetStore(_db(tmp_path))
        store.save_asset(_asset())
        got = store.get_asset("a1")
        assert got is not None
        assert got.asset_id == "a1"
        assert got.asset_type == AssetType.MARKDOWN
        assert got.metadata["title"] == "Titulo Prueba"
        assert got.source.kind == "web"
        assert got.source.location == "https://x.com"
        assert got.relationships[0].target_id == "a2"
        assert got.relationships[0].relation == "cites"
        assert got.relationships[0].metadata == {"k": 1}
        assert got.quality == 0.9

    def test_no_existe(self, tmp_path) -> None:
        assert SQLiteAssetStore(_db(tmp_path)).get_asset("ghost") is None

    def test_error(self, tmp_path) -> None:
        assert SQLiteAssetStore(tmp_path / "no-es-db").get_asset("a1") is None

    def test_row_sin_metadata_ni_source(self, tmp_path) -> None:
        path = _db(tmp_path)
        conn = sqlite3.connect(path)
        conn.execute(
            "INSERT INTO op_assets (id, asset_type) VALUES ('raw', 'pdf')"
        )
        conn.commit()
        conn.close()
        got = SQLiteAssetStore(path).get_asset("raw")
        assert got is not None
        assert got.metadata == {}
        assert got.source.kind == "unknown"
        assert got.relationships == ()
        assert got.quality == 0.0


class TestExistsDelete:
    def test_exists(self, tmp_path) -> None:
        store = SQLiteAssetStore(_db(tmp_path))
        store.save_asset(_asset())
        assert store.asset_exists("a1") is True
        assert store.asset_exists("zz") is False

    def test_exists_error(self, tmp_path) -> None:
        assert SQLiteAssetStore(tmp_path / "no-es-db").asset_exists("a1") is False

    def test_delete(self, tmp_path) -> None:
        store = SQLiteAssetStore(_db(tmp_path))
        store.save_asset(_asset())
        assert store.delete_asset("a1") is True
        assert store.asset_exists("a1") is False

    def test_delete_error(self, tmp_path) -> None:
        assert SQLiteAssetStore(tmp_path / "no-es-db").delete_asset("a1") is False


class TestList:
    def _store(self, tmp_path) -> SQLiteAssetStore:
        path = _db(tmp_path)
        store = SQLiteAssetStore(path)
        store.save_asset(_asset("a1", asset_type=AssetType.MARKDOWN))
        store.save_asset(_asset("a2", title="Video Prueba", asset_type=AssetType.VIDEO))
        store.save_asset(_asset("a3", title="Imagen Prueba", asset_type=AssetType.IMAGE))
        return store

    def test_todos(self, tmp_path) -> None:
        items = self._store(tmp_path).list_assets()
        assert len(items) == 3

    def test_filtro_tipo(self, tmp_path) -> None:
        items = self._store(tmp_path).list_assets(asset_type=AssetType.VIDEO)
        assert [a.asset_id for a in items] == ["a2"]

    def test_limit_offset(self, tmp_path) -> None:
        items = self._store(tmp_path).list_assets(limit=2, offset=0)
        assert len(items) == 2
        items2 = self._store(tmp_path).list_assets(limit=2, offset=2)
        assert len(items2) == 1

    def test_error(self, tmp_path) -> None:
        assert SQLiteAssetStore(tmp_path / "no-es-db").list_assets() == []

    def test_count(self, tmp_path) -> None:
        store = self._store(tmp_path)
        assert store.count() == 3
        assert store.count(asset_type=AssetType.IMAGE) == 1

    def test_count_error(self, tmp_path) -> None:
        assert SQLiteAssetStore(tmp_path / "no-es-db").count() == 0


class TestSearch:
    def test_query_vacia(self, tmp_path) -> None:
        assert SQLiteAssetStore(_db(tmp_path)).search_assets("   ") == []

    def test_fts5_ok(self, tmp_path) -> None:
        store = SQLiteAssetStore(_db(tmp_path))
        store.save_asset(_asset("a1", title="motor de busqueda"))
        store.save_asset(_asset("a2", title="otro tema"))
        items = store.search_assets("motor")
        assert [a.asset_id for a in items] == ["a1"]

    def test_fts5_con_tipo(self, tmp_path) -> None:
        store = SQLiteAssetStore(_db(tmp_path))
        store.save_asset(_asset("a1", title="motor video", asset_type=AssetType.VIDEO))
        store.save_asset(_asset("a2", title="motor doc", asset_type=AssetType.PDF))
        items = store.search_assets("motor", asset_type=AssetType.PDF)
        assert [a.asset_id for a in items] == ["a2"]

    def test_fallback_like_sin_fts(self, tmp_path) -> None:
        path = _db(tmp_path)
        store = SQLiteAssetStore(path)
        store.save_asset(_asset("a1", title="motor de busqueda"))
        store.save_asset(_asset("a2", title="otro tema"))
        conn = sqlite3.connect(path)
        conn.execute("DROP TABLE op_assets_fts")
        conn.commit()
        conn.close()
        items = store.search_assets("motor")
        assert [a.asset_id for a in items] == ["a1"]

    def test_fallback_like_con_tipo(self, tmp_path) -> None:
        path = _db(tmp_path)
        store = SQLiteAssetStore(path)
        store.save_asset(_asset("a1", title="motor video", asset_type=AssetType.VIDEO))
        store.save_asset(_asset("a2", title="motor pdf", asset_type=AssetType.PDF))
        conn = sqlite3.connect(path)
        conn.execute("DROP TABLE op_assets_fts")
        conn.commit()
        conn.close()
        items = store.search_assets("motor", asset_type=AssetType.VIDEO)
        assert [a.asset_id for a in items] == ["a1"]


class TestSanitize:
    def test_terminos_escapados(self) -> None:
        assert _sanitize_fts5('hello world "x"') == '"hello" "world" """x"""'

    def test_vacio(self) -> None:
        assert _sanitize_fts5("   ") == ""
