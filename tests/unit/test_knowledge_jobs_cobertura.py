"""Tests de cobertura para knowledge/engine/jobs.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.jobs import (
    _ejecutar_archive_job,
    _inc_job_retry,
    _mark_job_done,
    _mark_job_failed,
    _recover_stale_jobs,
    compile_worker,
    enqueue_archive_job,
    process_archive_jobs,
)
from knowledge.engine.lock import compile_lock
from knowledge.engine.sqlite_writer import init_db

SCHEMA = Path("schemas/knowledge_graph.sql")


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "j.db"
    init_db(path, SCHEMA)
    return path


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "src"
    repo.mkdir()
    (repo / "a.md").write_text("contenido")
    from knowledge.engine.archiver import _git_cmd

    _git_cmd("init", "-b", "main", cwd=repo)
    _git_cmd("add", ".", cwd=repo)
    _git_cmd("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init", cwd=repo)
    return repo


def _job_row(db: Path, job_id: int) -> dict:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM op_jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    assert row is not None, f"job {job_id} no existe"
    return dict(row)


def _insert_job(db: Path, payload: str = "{}", job_type: str = "archive_source") -> int:
    conn = sqlite3.connect(db)
    cur = conn.execute(
        "INSERT INTO op_jobs (job_type, status, payload, dedup_key, created_at) "
        "VALUES (?, 'pending', ?, 'k', datetime('now'))",
        (job_type, payload),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def test_enqueue_job(db, git_repo, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.archiver._DEFAULT_ARCHIVE_DIR", git_repo.parent / "arch")
    enqueue_archive_job(db, git_repo, "cid-1")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM op_jobs").fetchall()
    conn.close()
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload"])
    assert payload["source_dir"] == str(git_repo)


def test_enqueue_job_dedup(db, git_repo) -> None:
    enqueue_archive_job(db, git_repo)
    enqueue_archive_job(db, git_repo)
    n = sqlite3.connect(db).execute("SELECT COUNT(*) FROM op_jobs").fetchone()[0]
    assert n == 1


def test_enqueue_job_error_no_crash(tmp_path) -> None:
    enqueue_archive_job(tmp_path / "no.db", tmp_path)
    assert True


def test_ejecutar_archive_job_ok(db, git_repo, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.archiver._DEFAULT_ARCHIVE_DIR", git_repo.parent / "arch")
    enqueue_archive_job(db, git_repo, "cid")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    job = conn.execute("SELECT * FROM op_jobs").fetchone()
    _ejecutar_archive_job(conn, job, db, "cid")
    conn.commit()
    conn.close()
    row = _job_row(db, job["id"])
    assert row["status"] == "completed"
    assert (git_repo.parent / "arch").is_dir()


def test_ejecutar_archive_job_source_relativo(db, tmp_path) -> None:
    jid = _insert_job(db, json.dumps({"source_dir": "relativo", "db_path": str(db)}))
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    job = conn.execute("SELECT * FROM op_jobs WHERE id=?", (jid,)).fetchone()
    _ejecutar_archive_job(conn, job, db, "")
    conn.commit()
    conn.close()
    row = _job_row(db, jid)
    assert row["status"] == "failed"
    assert "absoluto" in row["error"]


def test_ejecutar_archive_job_db_relativo(db, tmp_path) -> None:
    jid = _insert_job(db, json.dumps({"source_dir": str(tmp_path), "db_path": "relativa.db"}))
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    job = conn.execute("SELECT * FROM op_jobs WHERE id=?", (jid,)).fetchone()
    _ejecutar_archive_job(conn, job, db, "")
    conn.commit()
    conn.close()
    row = _job_row(db, jid)
    assert row["status"] == "failed"


def test_ejecutar_archive_job_archiver_falla(db, tmp_path, monkeypatch) -> None:
    def _boom(*a, **k):
        raise ValueError("no es repo")

    monkeypatch.setattr("knowledge.engine.archiver.archive_source", _boom)
    jid = _insert_job(db, json.dumps({"source_dir": str(tmp_path)}))
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    job = conn.execute("SELECT * FROM op_jobs WHERE id=?", (jid,)).fetchone()
    _ejecutar_archive_job(conn, job, db, "")
    conn.commit()
    conn.close()
    row = _job_row(db, jid)
    assert row["status"] == "failed"
    assert "no es repo" in row["error"]


def test_process_archive_jobs_completa(db, git_repo, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.archiver._DEFAULT_ARCHIVE_DIR", git_repo.parent / "arch")
    enqueue_archive_job(db, git_repo, "cid")
    process_archive_jobs(db, "cid")
    n = sqlite3.connect(db).execute("SELECT COUNT(*) FROM op_jobs WHERE status='completed'").fetchone()[0]
    assert n == 1


def test_process_archive_jobs_stale_recovery(db, git_repo, monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.archiver._DEFAULT_ARCHIVE_DIR", git_repo.parent / "arch")
    enqueue_archive_job(db, git_repo, "cid")
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE op_jobs SET status='running', started_at=datetime('now', '-1 hour') WHERE id=1"
    )
    conn.commit()
    conn.close()
    process_archive_jobs(db, "cid")
    row = _job_row(db, 1)
    assert row["status"] == "completed"


def test_process_archive_jobs_error_no_crash(tmp_path) -> None:
    process_archive_jobs(tmp_path / "no.db", "cid")
    assert True


def test_recover_stale_directo(db) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO op_jobs (job_type, status, payload, dedup_key, created_at, started_at) "
        "VALUES ('archive_source', 'running', '{}', 'k', datetime('now'), datetime('now', '-1 hour'))"
    )
    conn.execute(
        "INSERT INTO op_jobs (job_type, status, payload, dedup_key, created_at, started_at) "
        "VALUES ('archive_source', 'running', '{}', 'k2', datetime('now'), datetime('now', '-1 minute'))"
    )
    conn.commit()
    _recover_stale_jobs(conn)
    conn.commit()
    rows = conn.execute(
        "SELECT id, status, error FROM op_jobs WHERE status='pending'"
    ).fetchall()
    assert len(rows) == 1
    assert "stale" in rows[0][2]
    conn.close()


def test_inc_job_retry(db) -> None:
    _inc_job_retry("archive_source", "stale", 2)
    assert True


def test_inc_job_retry_metrics_roto(db, monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("metrics caidas")

    monkeypatch.setattr("knowledge.engine.metrics.job_retry_total", _boom)
    _inc_job_retry("x", "y")
    assert True


def test_compile_worker_sin_jobs(db, tmp_path) -> None:
    assert compile_worker(db, tmp_path) == 0


def test_compile_worker_completa_job(db, tmp_path) -> None:
    src = tmp_path / "src"
    docs = src / "docs"
    docs.mkdir(parents=True)
    (docs / "a.md").write_text(
        "---\ntitle: A\ndoc_type: doc\n---\nContenido largo de prueba para compilar correctamente."
    )
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO op_jobs (job_type, status, payload, dedup_key, created_at) "
        "VALUES ('compile', 'pending', '{}', 'k', datetime('now'))"
    )
    conn.commit()
    conn.close()
    assert compile_worker(db, src) == 1
    assert _job_row(db, 1)["status"] == "completed"


def test_compile_worker_lock_ocupado(db, tmp_path) -> None:
    jid = _insert_job(db, job_type="compile")
    with compile_lock():
        assert compile_worker(db, tmp_path) == 0
    assert _job_row(db, jid)["status"] == "pending"


def test_compile_worker_job_falla(db, tmp_path) -> None:
    src = tmp_path / "src"
    docs = src / "docs"
    docs.mkdir(parents=True)
    (docs / "malo.md").write_text(
        "---\ntitle: Malo\ndoc_type: tipo_inexistente_xyz\n---\nContenido con tipo invalido para fallar compile."
    )
    jid = _insert_job(db, job_type="compile")
    compile_worker(db, src)
    assert _job_row(db, jid)["status"] == "failed"


def test_compile_worker_error_lectura(tmp_path) -> None:
    assert compile_worker(tmp_path / "no.db", tmp_path) == 0


def test_mark_job_done(db) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO op_jobs (job_type, status, payload, dedup_key, created_at) "
        "VALUES ('compile', 'pending', '{}', 'k', datetime('now'))"
    )
    conn.commit()
    conn.close()
    _mark_job_done(db, 1)
    assert _job_row(db, 1)["status"] == "completed"


def test_mark_job_done_error(tmp_path) -> None:
    _mark_job_done(tmp_path / "no.db", 1)
    assert True


def test_mark_job_failed(db) -> None:
    jid = _insert_job(db)
    _mark_job_failed(db, jid, "boom")
    assert _job_row(db, jid)["status"] == "failed"


def test_mark_job_failed_error(tmp_path) -> None:
    _mark_job_failed(tmp_path / "no.db", 1, "x")
    assert True
