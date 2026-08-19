"""Tests de cobertura para knowledge/engine/reader.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.models import (
    CompileContext,
    CompileOptions,
    Document,
    Frontmatter,
    KnowledgeObject,
    Relation,
)
from knowledge.engine.reader import (
    KnowledgeReader,
    _get_conn,
    _make_snippet,
    _release_conn,
    _row_to_document,
    clear_all_caches,
    clear_all_connection_pools,
)
from knowledge.engine.sqlite_writer import apply_compile, init_db

SCHEMA = Path("schemas/knowledge_graph.sql")


def _obj(doc_id: str, title: str, doc_type: str = "doc", relations: tuple[Relation, ...] = ()) -> KnowledgeObject:
    doc = Document(
        doc_id=doc_id,
        doc_type=doc_type,
        path=f"docs/{doc_id}.md",
        content_sha256=f"sha{doc_id}",
        frontmatter=Frontmatter(title=title, doc_type=doc_type),
        body=f"Contenido del documento {title} con palabras suficientes para busqueda de pruebas.",
        quality=0.9,
        confidence=0.8,
        semantic={"topic": title.lower()},
    )
    return KnowledgeObject(document=doc, relations=relations)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "k.db"
    init_db(path, SCHEMA)
    ctx = CompileContext(options=CompileOptions())
    apply_compile(
        db_path=path,
        objects=[
            _obj("0123456789aa", "Alpha", relations=(Relation(src="0123456789aa", dst="0123456789bb", relation="ref"),)),
            _obj("0123456789bb", "Beta", relations=(Relation(src="0123456789bb", dst="0123456789cc", relation="ref"),)),
            _obj("0123456789cc", "Gamma"),
            _obj("0123456789dd", "SpecDoc", doc_type="spec"),
        ],
        ctx=ctx,
        errors=[],
        warnings=[],
    )
    return path


def test_get_document_cacheador(db) -> None:
    reader = KnowledgeReader(db)
    doc = reader.get_document("0123456789aa")
    assert doc is not None
    assert doc.frontmatter.title == "Alpha"
    assert doc.semantic == {"topic": "alpha"}
    reader.clear_cache()
    assert reader.get_document("0123456789aa") is not None


def test_get_document_no_existe(db) -> None:
    reader = KnowledgeReader(db)
    assert reader.get_document("000000000000") is None


def test_cache_document_evicta(db) -> None:
    reader = KnowledgeReader(db)
    for i in range(120):
        reader._cache_document(f"doc-{i}", _obj(f"0123456789{i:02d}", f"T{i}").document)
    assert len(reader._doc_cache) <= 100


def test_get_document_cache_move_to_end(db) -> None:
    reader = KnowledgeReader(db)
    reader.get_document("0123456789aa")
    reader.get_document("0123456789aa")
    assert next(reversed(reader._doc_cache)) == "0123456789aa"


def test_clear_all_caches(db) -> None:
    reader = KnowledgeReader(db)
    reader.get_document("0123456789aa")
    assert len(reader._doc_cache) == 1
    clear_all_caches()
    assert len(reader._doc_cache) == 0


def test_row_to_document(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM kg_nodes WHERE id='0123456789aa'").fetchone()
    conn.close()
    doc = _row_to_document(row)
    assert doc.doc_id == "0123456789aa"
    assert doc.quality == 0.9


def test_search_lexical(db) -> None:
    reader = KnowledgeReader(db)
    results = reader.search("Alpha", mode="lexical")
    assert len(results) >= 1
    assert results[0].doc_id == "0123456789aa"
    assert results[0].title == "Alpha"
    assert "Alpha" in results[0].snippet or results[0].snippet


def test_search_filtro_tipo(db) -> None:
    reader = KnowledgeReader(db)
    results = reader.search("Contenido", filters={"type": "spec"})
    assert all(r.doc_type == "spec" for r in results)


def test_search_filtro_path(db) -> None:
    reader = KnowledgeReader(db)
    results = reader.search("Contenido", filters={"path_prefix": "docs/0123456789"})
    assert len(results) >= 1


def test_search_sin_resultados(db) -> None:
    reader = KnowledgeReader(db)
    assert reader.search("zzzznada", mode="lexical") == []


def test_search_modo_invalido(db) -> None:
    reader = KnowledgeReader(db)
    with pytest.raises(ValueError):
        reader.search("x", mode="magico")


def test_search_hybrid_fallback_lexical(db, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.reader.search_semantic", lambda *a, **k: [])
    reader = KnowledgeReader(db)
    results = reader.search("Alpha", mode="hybrid")
    assert len(results) >= 1


def test_search_hybrid_rrf(db, monkeypatch) -> None:
    monkeypatch.setattr(
        "knowledge.engine.reader.search_semantic",
        lambda *a, **k: [
            {"doc_id": "0123456789aa", "text": "txt Alpha", "title": "Alpha", "doc_type": "doc"},
            {"doc_id": "0123456789bb", "text": "txt Beta", "title": "Beta", "doc_type": "doc"},
        ],
    )
    monkeypatch.setattr("knowledge.engine.reader.get_pending_delete_ids", lambda *a: set())
    reader = KnowledgeReader(db)
    results = reader.search("Alpha", mode="hybrid", limit=5)
    assert len(results) >= 1
    assert results[0].doc_id in ("0123456789aa", "0123456789bb")


def test_search_hybrid_excluye_pending_delete(db, monkeypatch) -> None:
    monkeypatch.setattr(
        "knowledge.engine.reader.search_semantic",
        lambda *a, **k: [{"doc_id": "0123456789aa", "text": "t", "title": "T", "doc_type": "doc"}],
    )
    monkeypatch.setattr("knowledge.engine.reader.get_pending_delete_ids", lambda *a: {"0123456789aa"})
    reader = KnowledgeReader(db)
    results = reader.search("Contenido", mode="hybrid", limit=5)
    assert "0123456789aa" not in [r.doc_id for r in results]


def test_related_todos(db) -> None:
    reader = KnowledgeReader(db)
    rels = reader.related("0123456789aa", depth=3)
    assert len(rels) == 2  # aa→bb y bb→cc


def test_related_filtro_relation(db) -> None:
    reader = KnowledgeReader(db)
    rels = reader.related("0123456789aa", relation="ref", depth=3)
    assert len(rels) == 2


def test_related_sin_resultados(db) -> None:
    reader = KnowledgeReader(db)
    assert reader.related("000000000000", depth=2) == []


def test_graph_sin_root(db) -> None:
    reader = KnowledgeReader(db)
    nodes = reader.graph()
    assert len(nodes) == 4


def test_graph_con_root(db) -> None:
    reader = KnowledgeReader(db)
    nodes = reader.graph(root="0123456789aa", depth=2)
    assert {n.doc_id for n in nodes} == {"0123456789aa", "0123456789bb"}
    nodes2 = reader.graph(root="0123456789aa", depth=3)
    assert {n.doc_id for n in nodes2} == {"0123456789aa", "0123456789bb", "0123456789cc"}


def test_graph_root_no_existe(db) -> None:
    reader = KnowledgeReader(db)
    assert reader.graph(root="000000000000", depth=2) == []


def test_get_conn_pool(db, monkeypatch) -> None:
    import knowledge.engine.reader as reader_mod

    monkeypatch.setattr(reader_mod, "_READER_POOL_MAX", 1)
    c1 = _get_conn(db)
    _release_conn(c1, db)
    c2 = _get_conn(db)
    _release_conn(c2, db)
    assert c1 is not None


def test_release_conn_pool_inexistente(db) -> None:
    conn = _get_conn(db)
    clear_all_connection_pools()
    _release_conn(conn, db)  # pool ya no existe → close
    assert True


def test_clear_pools(db) -> None:
    _get_conn(db)
    clear_all_connection_pools()
    assert True


def test_make_snippet() -> None:
    assert _make_snippet("", "q") == ""
    assert _make_snippet("cuerpo", "") == "cuerpo"
    assert _make_snippet("hola mundo", "hola") == "hola mundo"
    assert _make_snippet("sin match aqui", "zzz") == "sin match aqui"
    assert _make_snippet("palabras antes antes antes antes antes antes antes antes antes antes antes antes antes antes antes antes antes X medio cuerpo", "X")
    multi = _make_snippet("texto con varias palabras para probar", "varias palabras")
    assert "varias" in multi
    assert _make_snippet("x" * 500 + "a", "a").startswith("…")


def test_related_ciclo_no_infinito(db) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO kg_edges (src, dst, relation, metadata) VALUES ('0123456789cc', '0123456789aa', 'ref', NULL)"
    )
    conn.commit()
    conn.close()
    reader = KnowledgeReader(db)
    rels = reader.related("0123456789aa", depth=5)
    assert len(rels) <= 5
