"""Tests de cobertura para knowledge/engine/orchestrator.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.eventbus import CompileCompleted, get_bus
from knowledge.engine.orchestrator import (
    _default_dedup_key,
    _execute_compile,
    _finalizar_compile,
    compile_result_to_claims,
    compile_worker,
    request_compile,
)


class _Result:
    def __init__(self, success: bool, changed: int = 1, total: int = 2, errors: list | None = None) -> None:
        self.success = success
        self.documents_changed = changed
        self.documents_total = total
        self.errors = errors or []


def test_default_dedup_key() -> None:
    assert _default_dedup_key(None) == _default_dedup_key({})
    assert _default_dedup_key({"b": 1, "a": 2}) == _default_dedup_key({"a": 2, "b": 1})
    assert len(_default_dedup_key({"x": 1})) == 16


def test_finalizar_success(monkeypatch) -> None:
    seen: list[CompileCompleted] = []
    get_bus().subscribe(CompileCompleted, lambda e: seen.append(e))
    monkeypatch.setattr("knowledge.engine.orchestrator.record_compile", lambda **_: None)
    monkeypatch.setattr("knowledge.engine.orchestrator.enqueue_archive_job", lambda *_: None)
    monkeypatch.setattr("knowledge.engine.orchestrator.process_archive_jobs", lambda *_: None)
    _finalizar_compile(_Result(True), "test", "cid123", Path("/x"), Path("/y"))
    assert len(seen) == 1
    assert seen[0].reason == "test"
    assert seen[0].documents_changed == 1
    assert seen[0].correlation_id == "cid123"


def test_finalizar_failure_no_publish(monkeypatch) -> None:
    seen: list[CompileCompleted] = []
    get_bus().subscribe(CompileCompleted, lambda e: seen.append(e))
    monkeypatch.setattr("knowledge.engine.orchestrator.enqueue_archive_job", lambda *_: pytest.fail("no debe encolar"))
    _finalizar_compile(_Result(False, errors=[RuntimeError("boom")]), "test", "cid", Path("/x"), Path("/y"))
    assert seen == []


def test_execute_compile_exception(monkeypatch, tmp_path) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("compile falló")

    monkeypatch.setattr("knowledge.engine.orchestrator.compile_source", _boom)
    n = _execute_compile("test", "k", db_path=tmp_path / "d.db", source_dir=tmp_path)
    assert n == 0


def test_execute_compile_lock_acquisition(monkeypatch, tmp_path) -> None:
    class _LockError(Exception):
        pass

    from knowledge.engine import orchestrator

    def _locked():
        raise orchestrator.LockAcquisitionError

    monkeypatch.setattr("knowledge.engine.orchestrator.compile_lock", _locked)
    n = _execute_compile("test", "k", db_path=tmp_path / "d.db", source_dir=tmp_path)
    assert n == 0


def test_request_compile_ok(tmp_path) -> None:
    src = tmp_path / "source"
    docs = src / "docs"
    docs.mkdir(parents=True)
    (docs / "a.md").write_text("---\ntitle: A\ndoc_type: doc\n---\nContenido largo de prueba para compilar correctamente.")
    db = tmp_path / "k.db"
    from knowledge.engine.sqlite_writer import init_db

    init_db(db, Path("schemas/knowledge_graph.sql"))
    n = request_compile("test-ok", db_path=db, source_dir=src)
    assert n == 1
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT COUNT(*) AS c FROM kg_nodes").fetchone()
    conn.close()
    assert row["c"] >= 1


def test_request_compile_dedup_key(tmp_path) -> None:
    db = tmp_path / "k.db"
    assert request_compile("t", dedup_key="fijo", db_path=db, source_dir=tmp_path) in (0, 1)


def test_compile_result_to_claims(tmp_path) -> None:
    db = tmp_path / "c.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE kg_nodes (id TEXT PRIMARY KEY, type TEXT, path TEXT, frontmatter TEXT, body TEXT);"
    )
    conn.execute(
        "INSERT INTO kg_nodes VALUES ('n1', 'doc', 'docs/n1.md', ?, 'Cuerpo extenso de la nota uno.')",
        ('{"title": "Titulo Uno"}',),
    )
    conn.execute("INSERT INTO kg_nodes VALUES ('n2', 'doc', 'docs/n2.md', NULL, NULL)")
    conn.commit()
    conn.close()
    claims = compile_result_to_claims(db)
    assert len(claims) == 2
    c1 = claims[0]
    assert len(c1.id) == 16
    assert c1.subject == "doc"
    assert c1.predicate == "documents"
    assert c1.object == "Titulo Uno"
    assert "Titulo Uno" in c1.text
    assert c1.text_id == "n1"
    assert claims[1].text == "n2"


def test_compile_worker(tmp_path) -> None:
    db = tmp_path / "w.db"
    src = tmp_path / "src"
    src.mkdir()
    sqlite3.connect(db).close()
    n = compile_worker(db_path=db, source_dir=src)
    assert n == 0
