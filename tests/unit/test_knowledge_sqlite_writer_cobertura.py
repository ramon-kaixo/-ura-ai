"""Tests de cobertura para knowledge/engine/sqlite_writer.py."""

from __future__ import annotations

import json
import signal
import sqlite3
import threading
from pathlib import Path

import pytest

from knowledge.engine.models import (
    CompileContext,
    CompileError,
    CompileFeatures,
    CompileMetadata,
    CompileOptions,
    Document,
    Frontmatter,
    KnowledgeObject,
    Relation,
)
from knowledge.engine.sqlite_writer import (
    ActiveVersionRepository,
    CompilerRunRepository,
    NodeRepository,
    SyncPolicy,
    _build_result,
    _cancel_guard,
    _install_cancel_handler,
    _restore_cancel_handlers,
    apply_compile,
    get_compile_errors,
    init_db,
)

SCHEMA = Path("schemas/knowledge_graph.sql")


def _ctx() -> CompileContext:
    return CompileContext(
        metadata=CompileMetadata(
            run_id=7,
            source_commit="abc123",
            schema_version=15,
            features=CompileFeatures(parser_version="2.0", ontology_v1=True),
            correlation_id="cid-1",
        ),
        options=CompileOptions(compiler_version="0.1.0"),
    )


def _obj(doc_id: str, relations: tuple[Relation, ...] = ()) -> KnowledgeObject:
    doc = Document(
        doc_id=doc_id,
        doc_type="doc",
        path=f"docs/{doc_id}.md",
        content_sha256=f"sha{doc_id}",
        frontmatter=Frontmatter(title=f"T {doc_id}", doc_type="doc"),
        body=f"Cuerpo del documento {doc_id} con contenido suficiente.",
        quality=0.9,
        confidence=0.8,
        semantic={"topic": doc_id},
        embed_hash=None,
    )
    return KnowledgeObject(document=doc, relations=relations)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "k.db"
    init_db(path, SCHEMA)
    return path


def _count(db: Path, table: str) -> int:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    n = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]  # noqa: S608 — tabla fija en tests
    conn.close()
    return n


def test_init_db_crea_schema(tmp_path) -> None:
    db = tmp_path / "nueva.db"
    init_db(db, SCHEMA)
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for t in ("kg_nodes", "kg_edges", "kg_active_version", "op_compiler_runs", "op_compile_errors", "kg_nodes_fts"):
        assert t in tables


def test_init_db_error(monkeypatch, tmp_path) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("migración falló")

    monkeypatch.setattr("knowledge.engine.sqlite_writer.migrate_db", _boom)
    with pytest.raises(RuntimeError):
        init_db(tmp_path / "x.db", SCHEMA)


def test_init_db_ya_creada(db) -> None:
    init_db(db, SCHEMA)  # no-op
    assert db.exists()


def test_rebuild_inserta_nodos_y_edges(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    changed = NodeRepository.rebuild(
        conn,
        [_obj("a1", relations=(Relation(src="a1", dst="a2", relation="references"),))],
    )
    assert changed == 1
    row = conn.execute("SELECT id, type, path, content_sha256, quality, confidence FROM kg_nodes").fetchone()
    assert row["id"] == "a1"
    edge = conn.execute("SELECT src, dst, relation FROM kg_edges").fetchone()
    assert (edge["src"], edge["dst"], edge["relation"]) == ("a1", "a2", "references")
    conn.close()


def test_rebuild_sin_relaciones_y_fts_marcador(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    NodeRepository.rebuild(conn, [_obj("z1")])
    n = conn.execute("SELECT COUNT(*) AS c FROM kg_edges").fetchone()["c"]
    assert n == 0
    conn.close()


def test_delete_ids_vacio_no_operacion(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    NodeRepository.delete_ids(conn, [])
    assert _count(db, "kg_nodes") == 0
    conn.close()


def test_delete_ids_borra_nodos_y_edges(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    NodeRepository.rebuild(
        conn,
        [
            _obj("a1", relations=(Relation(src="a1", dst="b1", relation="ref"),)),
            _obj("b1"),
        ],
    )
    NodeRepository.delete_ids(conn, ["a1"])
    conn.commit()
    conn.close()
    assert _count(db, "kg_nodes") == 1
    assert _count(db, "kg_edges") == 0


def test_insert_errors_y_purge(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    err = CompileError(code="KE003", document="d1", stage="validator", message="tipo malo", line=2, column=3)
    warn = CompileError(code="KE009", document="d2", stage="validator", message="status raro")
    CompilerRunRepository.create_run(conn, _ctx(), 1, 1, [err], [warn], 12.5)
    row = conn.execute("SELECT error_code, severity, line, column FROM op_compile_errors").fetchall()
    conn.close()
    assert len(row) == 2
    assert (row[0]["error_code"], row[0]["severity"]) == ("KE003", "ERROR")
    assert (row[1]["error_code"], row[1]["severity"]) == ("KE009", "WARN")


def test_create_run_detalles(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    run_id = CompilerRunRepository.create_run(conn, _ctx(), 3, 5, [], [], 9.9)
    assert run_id > 0
    row = conn.execute(
        "SELECT status, documents_changed, documents_total, graph_version, compiler_version, details FROM op_compiler_runs"
    ).fetchone()
    assert row["status"] == "completed"
    assert row["documents_changed"] == 3
    assert row["documents_total"] == 5
    assert row["graph_version"] == 7
    details = json.loads(row["details"])
    assert details["correlation_id"] == "cid-1"
    assert details["cancelled"] is False
    assert details["schema_version"] == 15
    conn.close()


def test_active_version_swap(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    ActiveVersionRepository.swap(conn, 42, _ctx())
    row = conn.execute("SELECT graph_version, source_commit FROM kg_active_version WHERE singleton=1").fetchone()
    assert row["graph_version"] == 42
    assert row["source_commit"] == "abc123"
    ActiveVersionRepository.swap(conn, 43, _ctx())
    n = conn.execute("SELECT COUNT(*) AS c FROM kg_active_version").fetchone()["c"]
    assert n == 1
    conn.close()


def test_sync_full(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    NodeRepository.rebuild(conn, [_obj("a1")])
    SyncPolicy.sync_full(conn)
    row = conn.execute("SELECT id, title, body, tags FROM kg_nodes_fts WHERE id='a1'").fetchone()
    assert row["title"] == "T a1"
    assert "Cuerpo" in row["body"]
    assert row["tags"] == "doc"
    conn.close()


def test_sync_documents_delega(db) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    NodeRepository.rebuild(conn, [_obj("b1")])
    SyncPolicy.sync_documents(conn, ["b1"])
    n = conn.execute("SELECT COUNT(*) AS c FROM kg_nodes_fts").fetchone()["c"]
    assert n == 1
    conn.close()


def test_apply_compile_e2e(db, tmp_path) -> None:
    result = apply_compile(
        db,
        [_obj("a1", relations=(Relation(src="a1", dst="a2", relation="ref"),)), _obj("a2")],
        _ctx(),
        [],
        [],
    )
    assert result.success is True
    assert result.documents_changed == 2
    assert result.documents_total == 2
    assert result.graph_version == result.run_id and result.run_id > 0
    assert result.stage == "completed"
    assert _count(db, "kg_nodes") == 2
    assert _count(db, "kg_edges") == 1
    assert _count(db, "kg_nodes_fts") == 2
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    v = c.execute("SELECT graph_version FROM kg_active_version WHERE singleton=1").fetchone()
    c.close()
    assert v["graph_version"] == result.run_id


def test_apply_compile_con_deleted_ids(db) -> None:
    apply_compile(db, [_obj("keep")], _ctx(), [], [])
    apply_compile(db, [_obj("keep")], _ctx(), [], [], deleted_ids=["keep", "ghost"])
    assert _count(db, "kg_nodes") == 0
    assert _count(db, "kg_edges") == 0


def test_apply_compile_error_rollback(db, monkeypatch) -> None:
    def _boom(conn, objects):
        raise sqlite3.OperationalError("rotura simulada")

    monkeypatch.setattr(NodeRepository, "rebuild", staticmethod(_boom))
    with pytest.raises(sqlite3.OperationalError):
        apply_compile(db, [_obj("x")], _ctx(), [], [])
    assert _count(db, "kg_nodes") == 0


def test_build_result() -> None:
    err = CompileError(code="KE003", document="d", stage="v", message="m")
    res = _build_result(0.0, 5, 2, 3, _ctx(), [err], [])
    assert res.success is False
    assert res.graph_version == 5
    assert len(res.errors) == 1
    assert res.duration_ms >= 0


def test_get_compile_errors_vacio(db) -> None:
    assert get_compile_errors(db) == []


def test_get_compile_errors_con_datos(db) -> None:
    apply_compile(db, [_obj("a1")], _ctx(), [CompileError(code="KE009", document="x", stage="v", message="aviso")], [])
    rows = get_compile_errors(db, limit=1)
    assert len(rows) == 1
    assert rows[0]["error_code"] == "KE009"
    assert "document" in rows[0]


def test_cancel_guard_restaura_handlers() -> None:
    orig_int = signal.getsignal(signal.SIGINT)
    with _cancel_guard():
        assert signal.getsignal(signal.SIGINT) is not orig_int
    assert signal.getsignal(signal.SIGINT) is orig_int


def test_install_restore_en_thread() -> None:
    results: dict[str, bool] = {}

    def _run() -> None:
        before = signal.getsignal(signal.SIGINT)
        _install_cancel_handler()
        results["no_change"] = signal.getsignal(signal.SIGINT) is before
        _restore_cancel_handlers(None, None)

    t = threading.Thread(target=_run)
    t.start()
    t.join()
    assert results["no_change"] is True


def test_begin_immediate_with_retry_ok(db) -> None:
    from knowledge.engine.sqlite_writer import _begin_immediate_with_retry

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _begin_immediate_with_retry(conn, timeout=1.0)
    conn.commit()
    conn.close()


def test_get_conn_devuelve_conexion(db) -> None:
    from knowledge.engine.sqlite_writer import _get_conn

    conn = _get_conn(db)
    assert conn is not None
    conn.close()
