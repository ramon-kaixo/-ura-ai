"""Tests Fase 7 — Reconcile/Integration (split de test_fase7.py)."""
from __future__ import annotations

from pathlib import Path

from _fase7_helpers import (  # noqa: F401
    MagicMock,
    QdrantVectorStore,
    SQLiteAssetStore,
    SQLiteLineageStore,
    VectorAugmentedRetriever,
    _make_asset,
    json,
    mock_qdrant_client,
    sqlite3,
)


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

    def test_qdrant_list_ids_calls_scroll_endpoint(self, mock_qdrant_client):  # noqa: F811
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

    def test_qdrant_list_ids_pagination(self, mock_qdrant_client):  # noqa: F811
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

    def test_qdrant_list_ids_degraded(self, mock_qdrant_client):  # noqa: F811
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
