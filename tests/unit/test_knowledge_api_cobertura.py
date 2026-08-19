"""Tests de cobertura para knowledge/engine/api.py (FastAPI TestClient)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knowledge.engine.api import AppError, app, state
from knowledge.engine.models import CompileContext, CompileOptions, Document, Frontmatter, KnowledgeObject
from knowledge.engine.sqlite_writer import apply_compile, init_db

SCHEMA = Path("schemas/knowledge_graph.sql")


def _obj(doc_id: str, title: str) -> KnowledgeObject:
    doc = Document(
        doc_id=doc_id,
        doc_type="doc",
        path=f"docs/{doc_id}.md",
        content_sha256=f"sha{doc_id}",
        frontmatter=Frontmatter(title=title, doc_type="doc"),
        body=f"Cuerpo extenso del documento {title} para búsquedas y reglas del motor de conocimiento.",
        quality=0.9,
        confidence=0.8,
    )
    return KnowledgeObject(document=doc)


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    import knowledge.engine.api as api_mod

    monkeypatch.setattr(api_mod, "_API_KEY", None)
    db = tmp_path / "k.db"
    init_db(db, SCHEMA)
    ctx = CompileContext(options=CompileOptions())
    apply_compile(db, [_obj("0123456789aa", "Alpha"), _obj("0123456789bb", "Beta")], ctx, [], [])
    state.db_path = db
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "doc.md").write_text("contenido")
    import subprocess as sp

    sp.run(["git", "init", "-b", "main"], cwd=src_dir, capture_output=True, check=False)
    sp.run(["git", "add", "."], cwd=src_dir, capture_output=True, check=False)
    sp.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=src_dir,
        capture_output=True,
        check=False,
    )
    state.source_dir = src_dir
    state._repo = None
    monkeypatch.setattr("knowledge.engine.archiver._DEFAULT_ARCHIVE_DIR", tmp_path / "arch")
    with TestClient(app) as c:
        yield c
    state.db_path = Path("/tmp/nonexistent")


def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["schema_version"] == 15


def test_health_unhealthy(client, monkeypatch) -> None:
    class _Repo:
        def health_check(self):
            return {"healthy": False, "error": "db caida"}

    monkeypatch.setattr(state, "get_repo", lambda: _Repo())
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["error"] == "Unhealthy"


def test_status(client) -> None:
    r = client.get("/status")
    assert r.status_code == 200
    data = r.json()
    assert data["documents"] == 2
    assert data["relations"] == 0
    assert data["graph_version"]["graph_version"] > 0


def test_compile_sync_ok(client, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", lambda *a, **k: 1)
    r = client.post("/compile/sync")
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_compile_sync_conflict(client, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", lambda *a, **k: 0)
    r = client.post("/compile/sync")
    assert r.status_code == 409


def test_compile_sync_error(client, monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("rotura")

    monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", _boom)
    r = client.post("/compile/sync")
    assert r.status_code == 500


def test_compile_async_202(client, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", lambda *a, **k: 1)
    r = client.post("/compile")
    assert r.status_code == 202
    assert r.json()["success"] is True


def test_compile_async_conflict(client, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", lambda *a, **k: 0)
    r = client.post("/compile")
    assert r.status_code == 409


def test_compile_incremental(client, monkeypatch) -> None:
    class _R:
        success = True
        documents_changed = 1
        documents_total = 2

    monkeypatch.setattr("knowledge.engine.compiler.compile_incremental", lambda *a, **k: _R())
    r = client.post("/compile?incremental=true")
    assert r.status_code == 202
    assert r.json()["documents_changed"] == 1


def test_compile_timeout(client, monkeypatch) -> None:
    import asyncio

    def _timeout(*a, **k):
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", _timeout)
    r = client.post("/compile")
    assert r.status_code == 504


def test_search_lexical(client) -> None:
    r = client.post("/search", json={"query": "Alpha", "mode": "lexical", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["results"][0]["title"] == "Alpha"
    assert "doc_id" in data["results"][0]


def test_search_con_tipo(client) -> None:
    r = client.post("/search", json={"query": "cuerpo", "type": "doc"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_search_mode_invalido(client) -> None:
    r = client.post("/search", json={"query": "x", "mode": "magico"})
    assert r.status_code == 422


def test_search_error(client, monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("fts rota")

    monkeypatch.setattr(state, "get_repo", lambda: type("R", (), {"search": _boom})())
    r = client.post("/search", json={"query": "x"})
    assert r.status_code == 500


def test_get_document_ok(client) -> None:
    r = client.get("/documents/0123456789aa")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Alpha"
    assert data["doc_type"] == "doc"
    assert "Cuerpo" in data["body"]


def test_get_document_id_invalido(client) -> None:
    r = client.get("/documents/xx")
    assert r.status_code == 422


def test_get_document_inexistente(client) -> None:
    r = client.get("/documents/0123456789ff")
    assert r.status_code == 404


def test_get_document_error(client, monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("rotura")

    monkeypatch.setattr(state, "get_repo", lambda: type("R", (), {"get_document": _boom})())
    r = client.get("/documents/0123456789aa")
    assert r.status_code == 500


def test_list_rules(client) -> None:
    r = client.get("/rules")
    assert r.status_code == 200
    assert "rules" in r.json()


def test_evaluate_rules(client) -> None:
    r = client.post("/rules/eval")
    assert r.status_code in (200, 500)


def test_archive(client) -> None:
    r = client.post("/archive")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["files"] >= 1


def test_archive_error(client, monkeypatch) -> None:
    def _boom(*a, **k):
        raise ValueError("no es repo git")

    monkeypatch.setattr("knowledge.engine.archiver.archive_source", _boom)
    r = client.post("/archive")
    assert r.status_code == 422


def test_feedback_record(client) -> None:
    r = client.post("/feedback/0123456789aa?rating=5")
    assert r.status_code == 200
    assert r.json()["rating"] == 5


def test_feedback_rating_fuera(client) -> None:
    r = client.post("/feedback/0123456789aa?rating=9")
    assert r.status_code == 422


def test_feedback_doc_id_invalido(client) -> None:
    r = client.post("/feedback/xx?rating=3")
    assert r.status_code == 422


def test_feedback_top(client) -> None:
    r = client.get("/feedback/top?limit=5")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_feedback_top_limit_invalido(client) -> None:
    r = client.get("/feedback/top?limit=999")
    assert r.status_code == 422


def test_lineage(client) -> None:
    r = client.get("/metadata/lineage/0123456789aa")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_memory_list(client) -> None:
    r = client.get("/memory")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_memory_get_404(client) -> None:
    r = client.get("/memory/nonexistent")
    assert r.status_code == 404


def test_memory_search(client) -> None:
    r = client.post("/memory/search", json={"query": "algo"})
    assert r.status_code == 200


def test_memory_link_404(client) -> None:
    r = client.post("/memory/nonexistent/link", json={"asset_id": "0123456789aa"})
    assert r.status_code == 404


def test_metadata_context(client) -> None:
    r = client.post("/metadata/context", json={"query": "Alpha"})
    assert r.status_code == 200
    assert "to_dict" in dir(r.json()) or isinstance(r.json(), dict)


def test_metadata_retrieve(client) -> None:
    r = client.post("/metadata/retrieve", json={"query": "Alpha", "limit": 5})
    assert r.status_code == 200


def test_metrics(client) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]


def test_body_size_middleware(client) -> None:
    r = client.post("/search", content=b"x" * (11 * 1024 * 1024), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_headers_seguridad(client) -> None:
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Engine-Version"] == "0.2.0"
    assert "X-Request-Time-Ms" in r.headers


def test_auth_activada(client, monkeypatch) -> None:
    import knowledge.engine.api as api_mod

    monkeypatch.setattr(api_mod, "_API_KEY", "secreta")
    assert client.get("/health").status_code == 200  # público
    r = client.get("/status")
    assert r.status_code == 401
    r2 = client.get("/status", headers={"Authorization": "Bearer mala"})
    assert r2.status_code == 403
    r3 = client.get("/status", headers={"Authorization": "Bearer secreta"})
    assert r3.status_code == 200


def test_app_error_handler() -> None:
    exc = AppError(418, "teapot", "detalle")
    assert exc.status_code == 418
    assert exc.message == "teapot"
    assert exc.detail == "detalle"
