"""Tests para knowledge/engine/api.py — endpoints REST."""
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


class TestHealthStatus:
    def test_health(self, app) -> None:
        r = app.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_status(self, app, monkeypatch) -> None:
        def _execute(sql, *a, **k):
            if "FROM kg_nodes" in sql:
                return mock.Mock(**{"fetchone.return_value": {"c": 5}})
            if "FROM kg_edges" in sql:
                return mock.Mock(**{"fetchone.return_value": {"c": 3}})
            return mock.Mock(**{"fetchone.return_value": {"graph_version": "v1", "source_commit": "abc", "compiler_version": "c1"}})

        conn = mock.Mock()
        conn.execute.side_effect = _execute
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(return_value=conn))
        r = app.get("/status")
        assert r.status_code == 200
        assert r.json()["documents"] == 5
        assert r.json()["relations"] == 3


class TestCompile:
    def test_compile(self, app, monkeypatch) -> None:

        result = SimpleNamespace(success=True, documents_changed=3, documents_total=10)
        monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", mock.Mock(return_value=result))
        r = app.post("/compile")
        assert r.status_code == 202
        assert r.json()["message"] == "compile started"

    def test_compile_sync(self, app, monkeypatch) -> None:

        request = mock.Mock()
        request.return_value = SimpleNamespace(success=False, documents_changed=0)
        monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", request)
        r = app.post("/compile/sync")
        assert r.status_code == 200


class TestSearch:
    def test_search_ok(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        repo = mock.Mock(spec=["search"])
        result = SimpleNamespace(doc_id="d1", snippet="snippet", score=0.9, title="T", doc_type="doc")
        repo.search.return_value = [result]
        monkeypatch.setattr(api.state, "_repo", repo)
        r = app.post("/search", json={"query": "gato", "limit": 5})
        assert r.status_code == 200
        assert len(r.json()["results"]) == 1

    def test_search_sin_resultados(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        repo = mock.Mock(spec=["search"])
        repo.search.return_value = []
        monkeypatch.setattr(api.state, "_repo", repo)
        r = app.post("/search", json={"query": "nada"})
        assert r.status_code == 200
        assert r.json()["results"] == []


class TestDocuments:
    def test_get_document(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        repo = mock.Mock(spec=["get_document"])
        doc = SimpleNamespace(
            doc_id="abcd1234ef01",
            doc_type="doc",
            path="a.md",
            frontmatter=SimpleNamespace(title="T", tags=["x"]),
            body="contenido del documento",
        )
        repo.get_document.return_value = doc
        monkeypatch.setattr(api.state, "_repo", repo)
        r = app.get("/documents/abcd1234ef01")
        assert r.status_code == 200
        assert r.json()["doc_id"] == "abcd1234ef01"

    def test_get_document_no_existe(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        repo = mock.Mock(spec=["get_document"])
        repo.get_document.return_value = None
        monkeypatch.setattr(api.state, "_repo", repo)
        r = app.get("/documents/abcd1234ef01")
        assert r.status_code == 404


class TestRules:
    def test_list_rules(self, app, monkeypatch) -> None:

        with mock.patch("knowledge.engine.rules.list_rules", return_value=[]):
            r = app.get("/rules")
        assert r.status_code == 200

    def test_evaluate_rules(self, app, monkeypatch) -> None:
        from knowledge.engine import api

        repo = mock.Mock(spec=["get_documents_for_rules"])
        repo.get_documents_for_rules.return_value = ([], set(), set())
        monkeypatch.setattr(api.state, "_repo", repo)
        with mock.patch("knowledge.engine.rules.RuleEvaluator") as Evaluator:
            evaluator = mock.Mock()
            evaluator.evaluate.return_value = []
            Evaluator.return_value = evaluator
            r = app.post("/rules/eval")
        assert r.status_code == 200


class TestFeedback:
    def test_record_feedback(self, app, monkeypatch) -> None:

        with mock.patch("knowledge.engine.feedback.record_feedback", return_value=True):
            r = app.post("/feedback/abcd1234ef01", params={"rating": 4})
        assert r.status_code == 200

    def test_top_rated(self, app, monkeypatch) -> None:

        with mock.patch("knowledge.engine.feedback.top_rated", return_value=[]):
            r = app.get("/feedback/top")
        assert r.status_code == 200


class TestMetadata:
    def test_get_lineage(self, app, monkeypatch) -> None:

        with mock.patch("knowledge.engine.lineage_store.SQLiteLineageStore") as Store:
            store = mock.Mock()
            store.get_lineage.return_value = [
                {"event_type": "COMPLETE", "event_time": "t", "job_name": "j", "input_ids": "[]", "output_ids": "[]"}
            ]
            store.get_upstream.return_value = []
            store.get_downstream.return_value = []
            Store.return_value = store
            r = app.get("/metadata/lineage/a1")
        assert r.status_code == 200


class TestMemory:
    def test_list_memories(self, app, monkeypatch) -> None:

        with mock.patch("knowledge.engine.memory_store.SQLiteMemoryStore") as Store:
            store = mock.Mock(spec=["list"])
            store.list.return_value = []
            Store.return_value = store
            r = app.get("/memory")
        assert r.status_code == 200

    def test_get_memory(self, app, monkeypatch) -> None:

        with mock.patch("knowledge.engine.memory_store.SQLiteMemoryStore") as Store:
            store = mock.Mock(spec=["get"])
            store.get.return_value = None
            Store.return_value = store
            r = app.get("/memory/m1")
        assert r.status_code == 404
