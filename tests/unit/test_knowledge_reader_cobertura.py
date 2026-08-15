"""Cobertura 100x100 de knowledge/engine/reader.py (TASK-20260815-003).

Cubre KnowledgeReader (get_document, search lexical/hybrid, related, graph),
la gestión del pool de conexiones (_get_conn/_release_conn/clear_*),
_row_to_document y _make_snippet usando conexiones sqlite simuladas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from knowledge.engine import reader
from knowledge.engine.connection_pool import ReadConnectionPool
from knowledge.engine.models import (
    Document,
    Frontmatter,
    GraphNode,
    SearchResult,
)


class FakeRow(dict):
    """Fila sqlite3.Row simulada con acceso por clave."""


class FakeConn:
    """Conexión sqlite simulada. Coincide por subcadena SQL (orden importa)."""

    def __init__(self, results: dict[str, Any], default: Any = None) -> None:
        self._results = results
        self._default = default
        self.executed: list[tuple[str, Any]] = []
        self.closed = False

    def execute(self, sql: str, params: Any = ()) -> FakeConn:
        self.executed.append((sql, params))
        pkey = tuple(params) if params is not None else ()
        self._current = self._default
        for key, val in self._results.items():
            if key in sql:
                if isinstance(val, dict) and not isinstance(val, FakeRow):
                    self._current = val.get(pkey, val.get(()))
                else:
                    self._current = val
                break
        return self

    def fetchone(self) -> Any:
        return self._current

    def fetchall(self) -> Any:
        return self._current if self._current is not None else []

    def close(self) -> None:
        self.closed = True


def _patch_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sustituye ReadConnectionPool por un pool simulado sin sqlite."""

    def fake_init(self: Any, db_path: Path, max_connections: int = 5) -> None:
        self.db_path = db_path
        self.max_connections = max_connections
        self.acquires = 0
        self.closed = False
        self.released: list[Any] = []
        self._conn = FakeConn({})

    def fake_acquire(self: Any) -> FakeConn:
        self.acquires += 1
        return self._conn

    def fake_release(self: Any, conn: Any) -> None:
        self.released.append(conn)

    def fake_close_all(self: Any) -> None:
        self.closed = True

    monkeypatch.setattr(ReadConnectionPool, "__init__", fake_init)
    monkeypatch.setattr(ReadConnectionPool, "acquire", fake_acquire)
    monkeypatch.setattr(ReadConnectionPool, "release", fake_release)
    monkeypatch.setattr(ReadConnectionPool, "close_all", fake_close_all)


def _mk_doc(doc_id: str, title: str = "T") -> Document:
    return Document(
        doc_id=doc_id,
        doc_type="md",
        path=f"/p/{doc_id}",
        content_sha256="abc123",
        frontmatter=Frontmatter(title=title),
    )


@pytest.fixture(autouse=True)
def _reset_pools() -> None:
    reader._READER_POOL.clear()
    yield
    reader._READER_POOL.clear()


@pytest.fixture
def reader_and_conn(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Reader con _get_conn/_release_conn mockeados; devuelve (reader, conn, gets)."""

    def make(results: dict[str, Any], default: Any = None) -> tuple[reader.KnowledgeReader, FakeConn, list[int]]:
        conn = FakeConn(results, default)
        gets: list[int] = []

        def fake_get(_db_path: Path) -> FakeConn:
            gets.append(1)
            return conn

        monkeypatch.setattr(reader, "_get_conn", fake_get)
        monkeypatch.setattr(reader, "_release_conn", lambda _c, _db: None)
        r = reader.KnowledgeReader("/tmp/db.sqlite")
        return r, conn, gets

    return make


class TestPoolManagement:
    def test_get_conn_crea_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_pool(monkeypatch)
        conn = reader._get_conn(Path("a.sqlite"))
        assert isinstance(conn, FakeConn)
        assert list(reader._READER_POOL) == ["a.sqlite"]

    def test_get_conn_reutiliza_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_pool(monkeypatch)
        first = reader._get_conn(Path("a.sqlite"))
        second = reader._get_conn(Path("a.sqlite"))
        assert first is second
        assert reader._READER_POOL["a.sqlite"].acquires == 2

    def test_get_conn_evicta_pool_mas_antiguo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_pool(monkeypatch)
        for i in range(reader._READER_POOL_MAX):
            reader._get_conn(Path(f"d{i}.sqlite"))
        oldest = reader._READER_POOL["d0.sqlite"]
        reader._get_conn(Path("d10.sqlite"))
        assert len(reader._READER_POOL) == reader._READER_POOL_MAX
        assert "d0.sqlite" not in reader._READER_POOL
        assert oldest.closed
        assert "d10.sqlite" in reader._READER_POOL

    def test_release_conn_existente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_pool(monkeypatch)
        conn = reader._get_conn(Path("a.sqlite"))
        reader._release_conn(conn, Path("a.sqlite"))
        assert reader._READER_POOL["a.sqlite"].released == [conn]

    def test_release_conn_pool_perdido(self) -> None:
        conn = FakeConn({})
        reader._release_conn(conn, Path("nope.sqlite"))
        assert conn.closed

    def test_clear_all_connection_pools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_pool(monkeypatch)
        reader._get_conn(Path("a.sqlite"))
        reader._get_conn(Path("b.sqlite"))
        pools = list(reader._READER_POOL.values())
        reader.clear_all_connection_pools()
        assert reader._READER_POOL == {}
        assert all(p.closed for p in pools)


class TestClearAllCaches:
    def test_invalida_caches_de_todos_los_readers(self) -> None:
        r1 = reader.KnowledgeReader("/tmp/a.sqlite")
        r2 = reader.KnowledgeReader("/tmp/b.sqlite")
        r1._cache_document("d1", _mk_doc("d1"))
        r2._cache_document("d2", _mk_doc("d2"))
        reader.clear_all_caches()
        assert r1._doc_cache == {}
        assert r2._doc_cache == {}


class TestRowToDocument:
    def _row(self, **overrides: Any) -> FakeRow:
        data = {
            "id": "doc1",
            "type": "md",
            "path": "/p/doc1.md",
            "content_sha256": "sha",
            "frontmatter": '{"title": "Hola", "tags": ["a", "b"]}',
            "body": "cuerpo",
            "semantic": '{"emb": [1]}',
            "quality": 0.9,
            "confidence": 0.8,
            "embed_hash": "eh",
            "updated_at": "2026-01-01",
        }
        data.update(overrides)
        return FakeRow(data)

    def test_completo(self) -> None:
        doc = reader._row_to_document(self._row())
        assert doc.doc_id == "doc1"
        assert doc.frontmatter.title == "Hola"
        assert doc.frontmatter.tags == ("a", "b")
        assert doc.semantic == {"emb": [1]}
        assert doc.quality == 0.9
        assert doc.embed_hash == "eh"

    def test_semantic_vacio(self) -> None:
        doc = reader._row_to_document(self._row(semantic=None))
        assert doc.semantic == {}

    def test_body_quality_none(self) -> None:
        doc = reader._row_to_document(self._row(body=None, quality=None, confidence=None))
        assert doc.body == ""
        assert doc.quality == 0.0
        assert doc.confidence == 0.0


class TestGetDocument:
    def test_miss_devuelve_documento_y_cachea(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        row = FakeRow(
            {
                "id": "doc1",
                "type": "md",
                "path": "/p/doc1",
                "content_sha256": "sha",
                "frontmatter": '{"title": "T1"}',
                "body": "b",
                "semantic": "{}",
                "quality": 0.5,
                "confidence": 0.5,
                "embed_hash": "eh",
                "updated_at": "2026-01-01",
            }
        )
        r, conn, gets = reader_and_conn({"SELECT * FROM kg_nodes WHERE id = ?": row})
        doc = r.get_document("doc1")
        assert doc is not None
        assert doc.doc_id == "doc1"
        assert doc.frontmatter.title == "T1"
        assert len(gets) == 1
        assert len(conn.executed) == 1

    def test_cache_hit_no_consulta(self, reader_and_conn: Any) -> None:
        r, _conn, gets = reader_and_conn({})
        r._cache_document("doc1", _mk_doc("doc1"))
        doc = r.get_document("doc1")
        assert doc is not None
        assert gets == []

    def test_no_existe_devuelve_none(self, reader_and_conn: Any) -> None:
        r, _conn, gets = reader_and_conn({})
        assert r.get_document("missing") is None
        assert len(gets) == 1

    def test_evicta_entrada_mas_antigua(self, reader_and_conn: Any) -> None:
        r, _conn, _gets = reader_and_conn({})
        r._CACHE_MAXSIZE = 2
        r._cache_document("a", _mk_doc("a"))
        r._cache_document("b", _mk_doc("b"))
        r._cache_document("c", _mk_doc("c"))
        assert list(r._doc_cache) == ["b", "c"]

    def test_cache_hit_move_to_end(self, reader_and_conn: Any) -> None:
        r, _conn, _gets = reader_and_conn({})
        r._CACHE_MAXSIZE = 2
        r._cache_document("a", _mk_doc("a"))
        r._cache_document("b", _mk_doc("b"))
        r.get_document("a")
        r._cache_document("c", _mk_doc("c"))
        assert list(r._doc_cache) == ["a", "c"]

    def test_clear_cache(self, reader_and_conn: Any) -> None:
        r, _conn, _gets = reader_and_conn({})
        r._cache_document("a", _mk_doc("a"))
        r.clear_cache()
        assert r._doc_cache == {}


class TestSearch:
    def test_modo_invalido_raise_value_error(self, reader_and_conn: Any) -> None:
        r, _conn, _gets = reader_and_conn({})
        with pytest.raises(ValueError, match="Modo de búsqueda no soportado"):
            r.search("q", mode="vectorial")

    def test_audit_log_read_llamado(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, int]] = []

        class FakeAudit:
            def log_read(self, query: str = "", docs: int = 0, **_: Any) -> None:
                calls.append((query, docs))

        monkeypatch.setattr(reader, "get_audit", lambda: FakeAudit())
        row = FakeRow(
            {
                "id": "d1",
                "type": "md",
                "path": "/p/d1",
                "frontmatter": '{"title": "T"}',
                "body": "b",
                "rank": 1.0,
            }
        )
        r, _conn, _gets = reader_and_conn({"SELECT n.id, n.type, n.path, n.frontmatter, n.body, ": [row]})
        results = r.search("q", mode="lexical")
        assert len(results) == 1
        assert calls == [("q", 1)]

    def test_audit_fallo_se_suprime(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeAudit:
            def log_read(self, **_: Any) -> None:
                raise RuntimeError("boom")

        monkeypatch.setattr(reader, "get_audit", lambda: FakeAudit())
        r, _conn, _gets = reader_and_conn({})
        assert r.search("q", mode="lexical") == []


class TestSearchLexical:
    def _row(self, doc_id: str, rank: float | None = 1.0, **extra: Any) -> FakeRow:
        data = {
            "id": doc_id,
            "type": "md",
            "path": f"/p/{doc_id}",
            "frontmatter": f'{{"title": "T{doc_id}"}}',
            "body": "cuerpo con query",
            "rank": rank,
        }
        data.update(extra)
        return FakeRow(data)

    def test_basico(self, reader_and_conn: Any) -> None:
        r, conn, _gets = reader_and_conn(
            {"SELECT n.id, n.type, n.path, n.frontmatter, n.body, ": [self._row("d1"), self._row("d2", 2.5)]}
        )
        results = r._search_lexical("query", limit=10)
        assert [x.doc_id for x in results] == ["d1", "d2"]
        assert results[0].score == 1.0
        assert results[0].doc_type == "md"
        sql, params = conn.executed[0]
        assert "ORDER BY rank LIMIT ?" in sql
        assert params == ["query", 10]

    def test_rank_none_se_convierte_en_cero(self, reader_and_conn: Any) -> None:
        r, _conn, _gets = reader_and_conn(
            {"SELECT n.id, n.type, n.path, n.frontmatter, n.body, ": [self._row("d1", rank=None)]}
        )
        results = r._search_lexical("query", limit=10)
        assert results[0].score == 0.0

    def test_filtros_type_y_path_prefix(self, reader_and_conn: Any) -> None:
        r, conn, _gets = reader_and_conn({"SELECT n.id, n.type, n.path, n.frontmatter, n.body, ": [self._row("d1")]})
        results = r._search_lexical("query", filters={"type": "md", "path_prefix": "/p"}, limit=5)
        assert len(results) == 1
        sql, params = conn.executed[0]
        assert "AND n.type = ? " in sql
        assert "AND n.path LIKE ? " in sql
        assert params == ["query", "md", "/p%", 5]

    def test_filtro_solo_type(self, reader_and_conn: Any) -> None:
        r, conn, _gets = reader_and_conn({"SELECT n.id, n.type, n.path, n.frontmatter, n.body, ": [self._row("d1")]})
        r._search_lexical("query", filters={"type": "pdf"}, limit=10)
        sql, params = conn.executed[0]
        assert "AND n.type = ? " in sql
        assert "AND n.path LIKE ? " not in sql
        assert params == ["query", "pdf", 10]

    def test_filtro_solo_path_prefix(self, reader_and_conn: Any) -> None:
        r, conn, _gets = reader_and_conn({"SELECT n.id, n.type, n.path, n.frontmatter, n.body, ": [self._row("d1")]})
        r._search_lexical("query", filters={"path_prefix": "/p"}, limit=10)
        sql, params = conn.executed[0]
        assert "AND n.type = ? " not in sql
        assert "AND n.path LIKE ? " in sql
        assert params == ["query", "/p%", 10]

    def test_sin_resultados(self, reader_and_conn: Any) -> None:
        r, _conn, _gets = reader_and_conn({})
        assert r._search_lexical("query", limit=10) == []


class TestSearchHybrid:
    def test_semantic_vacio_fallback_lexical(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reader, "search_semantic", lambda query, top_k=5: [])
        expected = [SearchResult(doc_id="L1", score=1.0, title="t", snippet="s", doc_type="md")]
        monkeypatch.setattr(reader.KnowledgeReader, "_search_lexical", lambda self, q, filters=None, limit=10: expected)
        r, _conn, _gets = reader_and_conn({})
        assert r._search_hybrid("q", limit=10) == expected

    def test_merge_semantico_y_lexical(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        hits = [
            {"doc_id": "S1", "text": "texto sem", "title": "Sem", "score": 0.9},
            {"doc_id": "S2", "text": "texto 2", "title": "Sem2", "score": 0.8},
        ]
        monkeypatch.setattr(reader, "search_semantic", lambda query, top_k=5: hits)
        monkeypatch.setattr(reader, "get_pending_delete_ids", lambda db_path: ["S2"])
        lexical = [
            SearchResult(doc_id="S1", score=3.0, title="Sem", snippet="s", doc_type="md"),
            SearchResult(doc_id="L1", score=2.0, title="Lex", snippet="l", doc_type="pdf"),
        ]
        monkeypatch.setattr(reader.KnowledgeReader, "_search_lexical", lambda self, q, filters=None, limit=10: lexical)
        r, _conn, _gets = reader_and_conn({})
        results = r._search_hybrid("q", limit=10)
        ids = [x.doc_id for x in results]
        assert "S2" not in ids
        assert ids[0] == "S1"
        assert ids[1] == "L1"
        s1 = next(x for x in results if x.doc_id == "S1")
        assert s1.score > 1.0 / 60.0
        assert s1.doc_type == ""
        l1 = next(x for x in results if x.doc_id == "L1")
        assert l1.snippet == "l"
        assert l1.doc_type == "pdf"

    def test_hit_sin_doc_type_por_defecto(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        hits = [{"doc_id": "S1", "text": "t", "title": "x", "score": 0.9}]
        monkeypatch.setattr(reader, "search_semantic", lambda query, top_k=5: hits)
        monkeypatch.setattr(reader, "get_pending_delete_ids", lambda db_path: [])
        monkeypatch.setattr(reader.KnowledgeReader, "_search_lexical", lambda self, q, filters=None, limit=10: [])
        r, _conn, _gets = reader_and_conn({})
        results = r._search_hybrid("q", limit=10)
        assert results[0].doc_type == ""

    def test_limite_recorta_resultados(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        hits = [{"doc_id": f"S{i}", "text": "t", "title": "x", "score": 0.9} for i in range(5)]
        monkeypatch.setattr(reader, "search_semantic", lambda query, top_k=5: hits)
        monkeypatch.setattr(reader, "get_pending_delete_ids", lambda db_path: [])
        monkeypatch.setattr(reader.KnowledgeReader, "_search_lexical", lambda self, q, filters=None, limit=10: [])
        r, _conn, _gets = reader_and_conn({})
        results = r._search_hybrid("q", limit=2)
        assert len(results) == 2

    def test_duplicados_semanticos_acumulan_rrf(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        hits = [
            {"doc_id": "S1", "text": "a", "title": "x", "score": 0.9},
            {"doc_id": "S1", "text": "b", "title": "y", "score": 0.8},
        ]
        monkeypatch.setattr(reader, "search_semantic", lambda query, top_k=5: hits)
        monkeypatch.setattr(reader, "get_pending_delete_ids", lambda db_path: [])
        monkeypatch.setattr(reader.KnowledgeReader, "_search_lexical", lambda self, q, filters=None, limit=10: [])
        r, _conn, _gets = reader_and_conn({})
        results = r._search_hybrid("q", limit=10)
        assert len(results) == 1
        assert results[0].doc_id == "S1"
        assert results[0].score == pytest.approx(1.0 / 61.0 + 1.0 / 62.0)

    def test_lexical_en_pending_delete_se_omite(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        hits = [{"doc_id": "S1", "text": "t", "title": "x", "score": 0.9}]
        monkeypatch.setattr(reader, "search_semantic", lambda query, top_k=5: hits)
        monkeypatch.setattr(reader, "get_pending_delete_ids", lambda db_path: ["L1"])
        lexical = [SearchResult(doc_id="L1", score=2.0, title="Lex", snippet="l", doc_type="pdf")]
        monkeypatch.setattr(reader.KnowledgeReader, "_search_lexical", lambda self, q, filters=None, limit=10: lexical)
        r, _conn, _gets = reader_and_conn({})
        results = r._search_hybrid("q", limit=10)
        assert [x.doc_id for x in results] == ["S1"]

    def test_search_hybrid_via_metodo_publico(self, reader_and_conn: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reader, "search_semantic", lambda query, top_k=5: [])
        monkeypatch.setattr(reader, "get_audit", lambda: type("A", (), {"log_read": lambda self, **k: None})())
        expected = [SearchResult(doc_id="L1", score=1.0, title="t", snippet="s", doc_type="md")]
        monkeypatch.setattr(reader.KnowledgeReader, "_search_lexical", lambda self, q, filters=None, limit=10: expected)
        r, _conn, _gets = reader_and_conn({})
        assert r.search("q", mode="hybrid") == expected


class TestRelated:
    def test_sin_filtro_con_recursion(self, reader_and_conn: Any) -> None:
        edges_a = [
            FakeRow({"src": "A", "dst": "B", "relation": "refs", "metadata": '{"w": 1}'}),
            FakeRow({"src": "A", "dst": "C", "relation": "refs", "metadata": None}),
        ]
        edges_b = [FakeRow({"src": "B", "dst": "D", "relation": "refs", "metadata": "{}"})]
        r, conn, _gets = reader_and_conn(
            {"SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ?": {("A",): edges_a, ("B",): edges_b}}
        )
        results = r.related("A", depth=2)
        assert [x.dst for x in results] == ["B", "D", "C"]
        assert results[0].metadata == {"w": 1}
        assert results[1].metadata == {}
        assert len(conn.executed) == 3

    def test_con_filtro_de_relacion(self, reader_and_conn: Any) -> None:
        edges = [FakeRow({"src": "A", "dst": "B", "relation": "refs", "metadata": "{}"})]
        r, conn, _gets = reader_and_conn(
            {"SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ? AND relation = ?": {("A", "refs"): edges}}
        )
        results = r.related("A", relation="refs", depth=2)
        assert [x.dst for x in results] == ["B"]
        sql, params = conn.executed[0]
        assert "AND relation = ?" in sql
        assert params == ["A", "refs"]

    def test_depth_cero(self, reader_and_conn: Any) -> None:
        r, conn, _gets = reader_and_conn({})
        assert r.related("A", depth=0) == []
        assert conn.executed == []

    def test_visited_evita_ciclos(self, reader_and_conn: Any) -> None:
        edges_a = [FakeRow({"src": "A", "dst": "B", "relation": "refs", "metadata": "{}"})]
        edges_b = [FakeRow({"src": "B", "dst": "A", "relation": "refs", "metadata": "{}"})]
        r, conn, _gets = reader_and_conn(
            {"SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ?": {("A",): edges_a, ("B",): edges_b}}
        )
        results = r.related("A", depth=2)
        assert [x.dst for x in results] == ["B", "A"]
        assert len(conn.executed) == 2


class TestGraph:
    def test_root_none_lista_hasta_100(self, reader_and_conn: Any) -> None:
        rows = [
            FakeRow({"id": "d1", "type": "md", "path": "/p/d1", "frontmatter": '{"title": "T1"}'}),
            FakeRow({"id": "d2", "type": "md", "path": "/p/d2", "frontmatter": '{"title": "T2"}'}),
        ]
        edges = [FakeRow({"src": "d1", "dst": "d2", "relation": "refs", "metadata": "{}"})]
        r, conn, _gets = reader_and_conn(
            {
                "SELECT id, type, path, frontmatter FROM kg_nodes LIMIT 100": rows,
                "SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ?": edges,
            }
        )
        nodes = r.graph()
        assert [n.doc_id for n in nodes] == ["d1", "d2"]
        assert nodes[0].relations[0].dst == "d2"
        assert conn.executed

    def test_root_none_sin_nodos(self, reader_and_conn: Any) -> None:
        r, _conn, _gets = reader_and_conn({})
        assert r.graph() == []

    def test_con_root_recolecta_subgrafo(self, reader_and_conn: Any) -> None:
        row_a = FakeRow({"id": "A", "type": "md", "path": "/p/A", "frontmatter": '{"title": "TA"}'})
        row_b = FakeRow({"id": "B", "type": "md", "path": "/p/B", "frontmatter": '{"title": "TB"}'})
        edges_a = [FakeRow({"src": "A", "dst": "B", "relation": "refs", "metadata": "{}"})]
        r, conn, _gets = reader_and_conn(
            {
                "SELECT id, type, path, frontmatter FROM kg_nodes WHERE id = ?": {("A",): row_a, ("B",): row_b},
                "SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ?": edges_a,
                "SELECT dst FROM kg_edges WHERE src = ?": {("A",): [FakeRow({"dst": "B"})]},
            }
        )
        nodes = r.graph(root="A", depth=2)
        assert [n.doc_id for n in nodes] == ["A", "B"]
        assert nodes[0].relations[0].dst == "B"
        assert len(conn.executed) >= 3


class TestRowToGraphnode:
    def test_con_relaciones(self) -> None:
        row = FakeRow({"id": "d1", "type": "md", "path": "/p/d1", "frontmatter": '{"title": "T1"}'})
        conn = FakeConn(
            {
                "SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ?": [
                    FakeRow({"src": "d1", "dst": "d2", "relation": "refs", "metadata": '{"w":2}'})
                ]
            }
        )
        node = reader.KnowledgeReader("/tmp/x.sqlite")._row_to_graphnode(row, conn)
        assert isinstance(node, GraphNode)
        assert node.title == "T1"
        assert node.relations[0].dst == "d2"
        assert node.relations[0].metadata == {"w": 2}

    def test_sin_edges(self) -> None:
        row = FakeRow({"id": "d1", "type": "md", "path": "/p/d1", "frontmatter": '{"title": "T1"}'})
        conn = FakeConn({})
        node = reader.KnowledgeReader("/tmp/x.sqlite")._row_to_graphnode(row, conn)
        assert node.relations == ()


class TestCollectSubgraph:
    def test_depth_cero(self, reader_and_conn: Any) -> None:
        r, conn, _gets = reader_and_conn({})
        nodes: list[GraphNode] = []
        r._collect_subgraph(conn, "A", 0, set(), nodes)
        assert nodes == []
        assert conn.executed == []

    def test_visited_evita_repetir(self, reader_and_conn: Any) -> None:
        r, conn, _gets = reader_and_conn({})
        nodes: list[GraphNode] = []
        r._collect_subgraph(conn, "A", 2, {"A"}, nodes)
        assert nodes == []
        assert conn.executed == []

    def test_nodo_inexistente(self, reader_and_conn: Any) -> None:
        r, conn, _gets = reader_and_conn({})
        nodes: list[GraphNode] = []
        r._collect_subgraph(conn, "A", 2, set(), nodes)
        assert nodes == []
        assert conn.executed

    def test_recursion_hijos(self, reader_and_conn: Any) -> None:
        row_a = FakeRow({"id": "A", "type": "md", "path": "/p/A", "frontmatter": '{"title": "TA"}'})
        row_b = FakeRow({"id": "B", "type": "md", "path": "/p/B", "frontmatter": '{"title": "TB"}'})
        r, conn, _gets = reader_and_conn(
            {
                "SELECT id, type, path, frontmatter FROM kg_nodes WHERE id = ?": {("A",): row_a, ("B",): row_b},
                "SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ?": [],
                "SELECT dst FROM kg_edges WHERE src = ?": {("A",): [FakeRow({"dst": "B"})]},
            }
        )
        nodes: list[GraphNode] = []
        r._collect_subgraph(conn, "A", 2, set(), nodes)
        assert [n.doc_id for n in nodes] == ["A", "B"]


class TestMakeSnippet:
    def test_body_vacio(self) -> None:
        assert reader._make_snippet("", "q") == ""

    def test_query_vacio(self) -> None:
        body = "x" * 250
        assert reader._make_snippet(body, "") == body[:200]

    def test_no_encontrado(self) -> None:
        body = "abc " * 100
        assert reader._make_snippet(body, "zzz") == body[:200]

    def test_palabra_central_con_elipsis(self) -> None:
        body = "a" * 120 + "HOLA mundo" + "b" * 120
        snippet = reader._make_snippet(body, "hola", context_chars=100)
        assert "HOLA" in snippet
        assert snippet.startswith("…")
        assert snippet.endswith("…")

    def test_multi_palabra_usa_primera(self) -> None:
        body = "a" * 50 + "alpha beta" + "b" * 50
        snippet = reader._make_snippet(body, "alpha beta", context_chars=100)
        assert "alpha" in snippet

    def test_al_inicio_sin_prefijo(self) -> None:
        body = "HOLA" + "b" * 100
        snippet = reader._make_snippet(body, "hola", context_chars=100)
        assert not snippet.startswith("…")

    def test_al_final_sin_sufijo(self) -> None:
        body = "a" * 100 + "HOLA"
        snippet = reader._make_snippet(body, "hola", context_chars=100)
        assert not snippet.endswith("…")
