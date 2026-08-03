"""Tests para knowledge/engine/repository.py — SQLiteKnowledgeRepository."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest import mock

import pytest

from knowledge.engine.repository import SQLiteKnowledgeRepository


@pytest.fixture
def db_path(tmp_path) -> Path:
    db = tmp_path / "db.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE kg_nodes (id TEXT PRIMARY KEY, type TEXT, path TEXT, frontmatter TEXT, body TEXT)")
    conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT)")
    conn.execute("INSERT INTO kg_nodes VALUES ('n1', 'doc', 'a.md', '{\"title\": \"A\", \"tags\": [\"x\"]}', 'cuerpo a')")
    conn.execute("INSERT INTO kg_nodes VALUES ('n2', 'doc', 'b.md', NULL, 'cuerpo b')")
    conn.execute("INSERT INTO kg_edges VALUES ('n1', 'n2')")
    conn.commit()
    conn.close()
    return db


class TestSQLiteKnowledgeRepository:
    def test_get_document(self, db_path, monkeypatch) -> None:
        repo = SQLiteKnowledgeRepository(db_path)
        doc = mock.Mock()
        reader = mock.Mock()
        reader.get_document.return_value = doc
        monkeypatch.setattr("knowledge.engine.reader.KnowledgeReader", mock.Mock(return_value=reader))
        assert repo.get_document("n1") is doc
        reader.get_document.assert_called_once_with("n1")

    def test_search(self, db_path, monkeypatch) -> None:
        repo = SQLiteKnowledgeRepository(db_path)
        results = [mock.Mock()]
        reader = mock.Mock()
        reader.search.return_value = results
        monkeypatch.setattr("knowledge.engine.reader.KnowledgeReader", mock.Mock(return_value=reader))
        out = repo.search("q", mode="hybrid", filters={"type": "doc"}, limit=5)
        assert out is results
        reader.search.assert_called_once_with("q", mode="hybrid", filters={"type": "doc"}, limit=5)

    def test_related(self, db_path, monkeypatch) -> None:
        repo = SQLiteKnowledgeRepository(db_path)
        relations = [mock.Mock()]
        reader = mock.Mock()
        reader.related.return_value = relations
        monkeypatch.setattr("knowledge.engine.reader.KnowledgeReader", mock.Mock(return_value=reader))
        out = repo.related("n1", relation="links", depth=3)
        assert out is relations
        reader.related.assert_called_once_with("n1", relation_type="links", depth=3)

    def test_get_node_ids(self, db_path) -> None:
        repo = SQLiteKnowledgeRepository(db_path)
        assert repo.get_node_ids() == {"n1", "n2"}

    def test_get_relation_targets(self, db_path) -> None:
        repo = SQLiteKnowledgeRepository(db_path)
        assert repo.get_relation_targets() == {"n2"}

    def test_get_documents_for_rules(self, db_path) -> None:
        repo = SQLiteKnowledgeRepository(db_path)
        docs, node_ids, targets = repo.get_documents_for_rules()
        assert len(docs) == 2
        assert node_ids == {"n1", "n2"}
        assert targets == {"n2"}
        # n1 tiene frontmatter parseado
        doc1 = next(d for d in docs if d["id"] == "n1")
        assert doc1["title"] == "A"
        assert doc1["tags"] == ["x"]
        assert doc1["relations"] == ["n2"]
        # n2 sin frontmatter
        doc2 = next(d for d in docs if d["id"] == "n2")
        assert doc2["title"] == ""

    def test_health_check_ok(self, db_path) -> None:
        repo = SQLiteKnowledgeRepository(db_path)
        h = repo.health_check()
        assert h["healthy"] is True
        assert h["integrity"] == "ok"

    def test_health_check_error(self, tmp_path) -> None:
        """open_db crea la DB si falta (healthy True en vacia).
        El fallo real: DB corrupta (no sqlite)."""
        db = tmp_path / "corrupta.sqlite"
        db.write_bytes(b"no es sqlite")
        repo = SQLiteKnowledgeRepository(db)
        h = repo.health_check()
        assert h["healthy"] is False
        assert "error" in h
