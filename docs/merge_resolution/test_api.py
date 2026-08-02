"""Tests for api.py — RESOLUCION DE MERGE (Fase 5)."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knowledge.engine.api import app, state
from knowledge.engine.connection import open_db
from knowledge.engine.migrations import migrate_db

KEY = "${URA_API_KEY}"


@pytest.fixture
def client():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = open_db(db_path)
    migrate_db(conn, Path("./schemas/knowledge_graph.sql").resolve())
    conn.close()
    old_db, old_repo = state.db_path, state._repo
    state.db_path, state._repo = Path(db_path), None
    with TestClient(app) as c:
        yield c
    state.db_path, state._repo = old_db, old_repo
    Path(db_path).unlink(missing_ok=True)


def test_health(client):
    assert client.get("/health").status_code == 200


def test_status_auth(client):
    assert client.get("/status", headers={"Authorization": "Bearer " + KEY}).status_code == 200


def test_rules_auth(client):
    assert client.get("/rules", headers={"Authorization": "Bearer " + KEY}).status_code == 200


def test_doc_404_auth(client):
    assert client.get("/documents/000000000000", headers={"Authorization": "Bearer " + KEY}).status_code == 404


def test_metrics(client):
    assert client.get("/metrics").status_code == 200


def test_status_with_data(client):
    conn = open_db(state.db_path)
    conn.execute(
        "INSERT INTO kg_nodes (id,type,path,content_sha256,frontmatter,body,updated_at) "
        "VALUES ('n1','t','/n1.md','sha','{}','b','2024-01-01')"
    )
    conn.execute("INSERT INTO kg_edges (src,dst,relation,metadata) VALUES ('n1','n2','r','{}')")
    conn.commit()
    conn.close()
    r = client.get("/status", headers={"Authorization": "Bearer " + KEY})
    assert r.status_code == 200
    assert r.json()["documents"] == 1
    assert r.json()["relations"] == 1


def test_eval_rules_empty(client):
    r = client.post("/rules/eval", headers={"Authorization": "Bearer " + KEY})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["findings"] == []


def test_doc_found(client):
    conn = open_db(state.db_path)
    conn.execute(
        "INSERT INTO kg_nodes (id,type,path,content_sha256,frontmatter,body,updated_at) "
        "VALUES ('aabbccddeeff','doc','/test.md','sha256','{}','Body','2024-01-01')"
    )
    conn.commit()
    conn.close()
    r = client.get("/documents/aabbccddeeff", headers={"Authorization": "Bearer " + KEY})
    assert r.status_code == 200
    data = r.json()
    assert data["doc_id"] == "aabbccddeeff"
    assert data["doc_type"] == "doc"
