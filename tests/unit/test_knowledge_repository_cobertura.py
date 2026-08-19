"""Tests de cobertura para knowledge/engine/repository.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.engine.models import CompileContext, CompileOptions, Document, Frontmatter, KnowledgeObject, Relation
from knowledge.engine.repository import KnowledgeRepository, SQLiteKnowledgeRepository
from knowledge.engine.sqlite_writer import apply_compile, init_db

SCHEMA = Path("schemas/knowledge_graph.sql")


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "k.db"
    init_db(path, SCHEMA)
    objs = []
    for i, name in enumerate(("Alpha", "Beta")):
        doc = Document(
            doc_id=f"0123456789a{i}",
            doc_type="doc",
            path=f"docs/{name.lower()}.md",
            content_sha256=f"sha{i}",
            frontmatter=Frontmatter(title=name, doc_type="doc", tags=["tag"]),
            body=f"Contenido del documento {name} para busqueda de prueba.",
        )
        rels = (
            (Relation(src="0123456789a0", dst="0123456789a1", relation="ref"),)
            if i == 0
            else ()
        )
        objs.append(KnowledgeObject(document=doc, relations=rels))
    apply_compile(db_path=path, objects=objs, ctx=CompileContext(options=CompileOptions()), errors=[], warnings=[])
    return path


def test_repository_protocol_definido() -> None:
    for m in ("get_document", "search", "related", "get_node_ids", "get_relation_targets", "get_documents_for_rules", "health_check"):
        assert hasattr(KnowledgeRepository, m)


def test_get_document_ok(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    doc = repo.get_document("0123456789a0")
    assert doc is not None
    assert doc.frontmatter.title == "Alpha"


def test_get_document_no_existe(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    assert repo.get_document("000000000000") is None


def test_search_ok(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    results = repo.search("Alpha")
    assert any(r.doc_id == "0123456789a0" for r in results)


def test_search_filtros_y_limite(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    results = repo.search("Contenido", filters={"type": "doc"}, limit=1)
    assert len(results) == 1


def test_related_ok(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    rels = repo.related("0123456789a0", depth=2)
    assert len(rels) == 1
    assert rels[0].dst == "0123456789a1"


def test_related_filtro_relation(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    rels = repo.related("0123456789a0", relation="ref", depth=2)
    assert len(rels) == 1
    assert repo.related("0123456789a0", relation="otra", depth=2) == []


def test_get_node_ids(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    assert repo.get_node_ids() == {"0123456789a0", "0123456789a1"}


def test_get_relation_targets(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    assert repo.get_relation_targets() == {"0123456789a1"}


def test_get_documents_for_rules(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    docs, node_ids, targets = repo.get_documents_for_rules()
    assert node_ids == {"0123456789a0", "0123456789a1"}
    assert targets == {"0123456789a1"}
    by_id = {d["id"]: d for d in docs}
    assert by_id["0123456789a0"]["title"] == "Alpha"
    assert by_id["0123456789a0"]["tags"] == ["tag"]
    assert by_id["0123456789a0"]["relations"] == ["0123456789a1"]
    assert by_id["0123456789a1"]["relations"] == []


def test_health_check_ok(db) -> None:
    repo = SQLiteKnowledgeRepository(db)
    health = repo.health_check()
    assert health["healthy"] is True
    assert health["schema_version"] >= 15
    assert health["integrity"] == "ok"


def test_health_check_db_rota(tmp_path) -> None:
    repo = SQLiteKnowledgeRepository(tmp_path / "no-existe" / "k.db")
    health = repo.health_check()
    assert health["healthy"] is False
    assert "error" in health


def test_health_check_integridad_rota(tmp_path) -> None:
    path = tmp_path / "corrupt.db"
    path.write_bytes(b"no es una base sqlite")
    repo = SQLiteKnowledgeRepository(path)
    health = repo.health_check()
    assert health["healthy"] is False
