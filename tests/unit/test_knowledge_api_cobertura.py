"""Tests de cobertura de ramas de error/seguridad de knowledge/engine/api.py.

Cubre los caminos no ejercitados por test_knowledge_api.py: middleware
(401/403/413), health 503, status 500, compile 409/504/500, errores de
search/documents/rules, archive, feedback, memory y metadata endpoints.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    from knowledge.engine import api

    monkeypatch.setattr(api, "_API_KEY", None)
    monkeypatch.delenv("URA_API_KEY", raising=False)
    import sqlite3

    db = tmp_path / "db.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA user_version = 1")
    conn.execute("CREATE TABLE kg_nodes (id TEXT PRIMARY KEY, type TEXT, path TEXT, frontmatter TEXT, body TEXT)")
    conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT)")
    conn.commit()
    conn.close()
    api.state.db_path = db
    api.state.source_dir = tmp_path / "src"
    api.state._repo = None
    from fastapi.testclient import TestClient

    with TestClient(api.app) as client:
        yield client


class TestMiddlewareSeguridad:
    def test_401_sin_bearer(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        monkeypatch.setattr(api, "_API_KEY", "k-test")
        r = app.get("/status")
        assert r.status_code == 401

    def test_403_token_invalido(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        monkeypatch.setattr(api, "_API_KEY", "k-test")
        r = app.get("/status", headers={"Authorization": "Bearer malo"})
        assert r.status_code == 403

    def test_403_token_invalido_ok(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        monkeypatch.setattr(api, "_API_KEY", "k-test")
        repo = mock.Mock()
        repo.health_check.return_value = {"healthy": True, "schema_version": "3"}
        monkeypatch.setattr(api.state, "get_repo", lambda: repo)
        r = app.get("/health", headers={"Authorization": "Bearer k-test"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_413_body_demasiado_grande(self, app) -> None:
        r = app.post(
            "/search",
            content=b'{"query": "' + b"a" * (10 * 1024 * 1024 + 100) + b'"}',
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 413

    def test_cabeceras_seguridad(self, app) -> None:
        r = app.get("/health")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Engine-Version"] == "0.2.0"


class TestHealthStatusErrores:
    def test_health_unhealthy(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        repo = mock.Mock()
        repo.health_check.return_value = {"healthy": False, "error": "db caida"}
        monkeypatch.setattr(api.state, "get_repo", lambda: repo)
        r = app.get("/health")
        assert r.status_code == 503
        assert "db caida" in r.json()["detail"]

    def test_status_error(self, app, monkeypatch) -> None:
        def _boom(*a, **k):
            raise RuntimeError("tabla no existe")

        monkeypatch.setattr("knowledge.engine.connection.open_db", _boom)
        r = app.get("/status")
        assert r.status_code == 500

    def test_doc_id_invalido(self, app) -> None:
        r = app.get("/documents/no-valido")
        assert r.status_code == 422


class TestCompileErrores:
    def test_incremental(self, app, monkeypatch) -> None:
        result = SimpleNamespace(success=True, documents_changed=2, documents_total=5)
        monkeypatch.setattr("knowledge.engine.compiler.compile_incremental", mock.Mock(return_value=result))
        r = app.post("/compile?incremental=true")
        assert r.status_code == 202
        assert r.json()["message"] == "incremental"

    def test_conflict_409(self, app, monkeypatch) -> None:
        monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", mock.Mock(return_value=0))
        r = app.post("/compile")
        assert r.status_code == 409

    def test_timeout_504(self, app, monkeypatch) -> None:
        import asyncio

        def _boom(*a, **k):
            raise asyncio.TimeoutError("compile agotado")

        monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", _boom)
        r = app.post("/compile")
        assert r.status_code == 504

    def test_error_500(self, app, monkeypatch) -> None:
        def _boom(*a, **k):
            raise RuntimeError("compilador roto")

        monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", _boom)
        r = app.post("/compile")
        assert r.status_code == 500

    def test_sync_conflict_409(self, app, monkeypatch) -> None:
        monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", mock.Mock(return_value=0))
        r = app.post("/compile/sync")
        assert r.status_code == 409

    def test_sync_error_500(self, app, monkeypatch) -> None:
        def _boom(*a, **k):
            raise RuntimeError("sync roto")

        monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", _boom)
        r = app.post("/compile/sync")
        assert r.status_code == 500


class TestSearchErrores:
    def test_con_type_y_error(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        def _search(query, mode="lexical", filters=None, limit=10):
            raise RuntimeError("fts roto")

        repo = mock.Mock()
        repo.search.side_effect = _search
        monkeypatch.setattr(api.state, "get_repo", lambda: repo)
        r = app.post("/search", json={"query": "hola", "type": "guide", "mode": "lexical"})
        assert r.status_code == 500

    def test_get_document_error(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        repo = mock.Mock()
        repo.get_document.side_effect = RuntimeError("repo roto")
        monkeypatch.setattr(api.state, "get_repo", lambda: repo)
        r = app.get("/documents/0123456789ab")
        assert r.status_code == 500

    def test_rules_eval_error(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        repo = mock.Mock()
        repo.get_documents_for_rules.side_effect = RuntimeError("rules rotas")
        monkeypatch.setattr(api.state, "get_repo", lambda: repo)
        r = app.post("/rules/eval")
        assert r.status_code == 500


class TestArchive:
    def test_ok(self, app, monkeypatch) -> None:
        manifest = SimpleNamespace(
            source_commit="a" * 40,
            file_count=12,
            content_sha256="b" * 64,
        )
        monkeypatch.setattr("knowledge.engine.archiver.archive_source", mock.Mock(return_value=manifest))
        r = app.post("/archive")
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["files"] == 12

    def test_value_error_422(self, app, monkeypatch) -> None:
        def _boom(*a, **k):
            raise ValueError("source no es git repo")

        monkeypatch.setattr("knowledge.engine.archiver.archive_source", _boom)
        r = app.post("/archive")
        assert r.status_code == 422

    def test_error_500(self, app, monkeypatch) -> None:
        def _boom(*a, **k):
            raise RuntimeError("archivo roto")

        monkeypatch.setattr("knowledge.engine.archiver.archive_source", _boom)
        r = app.post("/archive")
        assert r.status_code == 500


class TestFeedbackErrores:
    def test_rating_fuera_rango(self, app) -> None:
        r = app.post("/feedback/0123456789ab?rating=0")
        assert r.status_code == 422

    def test_record_feedback_fallo(self, app, monkeypatch) -> None:
        monkeypatch.setattr("knowledge.engine.feedback.record_feedback", mock.Mock(return_value=False))
        r = app.post("/feedback/0123456789ab?rating=5")
        assert r.status_code == 500

    def test_top_limit_fuera_rango(self, app) -> None:
        r = app.get("/feedback/top?limit=0")
        assert r.status_code == 422


class TestMemoryEndpoints:
    def test_get_404(self, app, monkeypatch) -> None:
        store = mock.Mock()
        store.get.return_value = None
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        r = app.get("/memory/no-existe")
        assert r.status_code == 404

    def test_search(self, app, monkeypatch) -> None:
        record = mock.Mock()
        record.to_dict.return_value = {"id": "m1"}
        store = mock.Mock()
        store.search.return_value = [record]
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        r = app.post("/memory/search", json={"query": "hola"})
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_link_ok(self, app, monkeypatch) -> None:
        store = mock.Mock()
        store.link_asset.return_value = True
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        r = app.post("/memory/m1/link", json={"asset_id": "a1"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_link_404(self, app, monkeypatch) -> None:
        store = mock.Mock()
        store.link_asset.return_value = False
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        r = app.post("/memory/m1/link", json={"asset_id": "a1"})
        assert r.status_code == 404


class TestMetadataEndpoints:
    def test_context(self, app, monkeypatch) -> None:
        ctx = mock.Mock()
        ctx.to_dict.return_value = {"assets": [], "memories": []}
        retriever = mock.Mock()
        retriever.build_context.return_value = ctx
        monkeypatch.setattr("knowledge.engine.graphrag.SQLiteGraphRetriever", mock.Mock(return_value=retriever))
        r = app.post("/metadata/context", json={"query": "grafo"})
        assert r.status_code == 200
        assert r.json()["assets"] == []

    def test_retrieve(self, app, monkeypatch) -> None:
        ctx = mock.Mock()
        ctx.to_dict.return_value = {"assets": [{"id": "x"}]}
        retriever = mock.Mock()
        retriever.build_context.return_value = ctx
        monkeypatch.setattr("knowledge.engine.graphrag.SQLiteGraphRetriever", mock.Mock(return_value=retriever))
        r = app.post("/metadata/retrieve", json={"query": "mem"})
        assert r.status_code == 200
        assert r.json()["assets"] == [{"id": "x"}]

    def test_metrics(self, app, monkeypatch) -> None:
        monkeypatch.setattr("knowledge.engine.metrics.export_metrics", mock.Mock(return_value="metric 1"))
        r = app.get("/metrics")
        assert r.status_code == 200
        assert "metric 1" in r.text

