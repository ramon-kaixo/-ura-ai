"""Tests para knowledge/engine/jobs.py — op_jobs queue.

Usa sqlite real en tmp_path; mockea archiver/compiler/metrics/lock.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from knowledge.engine.jobs import compile_worker, enqueue_archive_job, process_archive_jobs

DDL = """
CREATE TABLE IF NOT EXISTS op_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    payload TEXT,
    dedup_key TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error TEXT,
    result_data TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_jobs_dedup ON op_jobs(dedup_key);
"""


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "kg.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(DDL)
    conn.commit()
    conn.close()
    return path


def _rows(db_path: Path, job_type: str = "archive_source") -> list[tuple]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT status, error FROM op_jobs WHERE job_type = ? ORDER BY id",
        (job_type,),
    ).fetchall()
    conn.close()
    return rows


def _insert(db_path: Path, job_type: str, status: str, payload: str = "{}", started_at: str | None = None) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO op_jobs (job_type, status, payload, created_at, started_at) VALUES (?, ?, ?, datetime('now'), ?)",
        (job_type, status, payload, started_at),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return int(job_id)


class TestEnqueue:
    def test_encola_job(self, db: Path) -> None:
        enqueue_archive_job(db, Path("/tmp/fuente"))
        rows = _rows(db)
        assert len(rows) == 1
        assert rows[0][0] == "pending"
        conn = sqlite3.connect(db)
        payload = json.loads(conn.execute("SELECT payload FROM op_jobs").fetchone()[0])
        conn.close()
        assert payload["source_dir"] == "/tmp/fuente"
        assert payload["db_path"] == str(db)

    def test_dedup_misma_fuente(self, db: Path) -> None:
        enqueue_archive_job(db, Path("/tmp/fuente"))
        enqueue_archive_job(db, Path("/tmp/fuente"))
        assert len(_rows(db)) == 1

    def test_fuentes_distintas(self, db: Path) -> None:
        enqueue_archive_job(db, Path("/tmp/a"))
        enqueue_archive_job(db, Path("/tmp/b"))
        assert len(_rows(db)) == 2

    def test_error_open_db(self, db: Path) -> None:
        with mock.patch("knowledge.engine.jobs.open_db", side_effect=RuntimeError("boom")):
            enqueue_archive_job(db, Path("/tmp/x"))  # no debe lanzar


class TestProcessArchiveJobs:
    def test_completa_job(self, db: Path) -> None:
        enqueue_archive_job(db, Path("/tmp/fuente"))
        with mock.patch("knowledge.engine.archiver.archive_source") as archive, mock.patch(
            "knowledge.engine.metrics.record_archive"
        ) as record:
            process_archive_jobs(db)
        assert _rows(db)[0][0] == "completed"
        archive.assert_called_once()
        record.assert_called_with(kind="source", status="completed")

    def test_falla_job(self, db: Path) -> None:
        enqueue_archive_job(db, Path("/tmp/fuente"))
        with mock.patch("knowledge.engine.archiver.archive_source", side_effect=RuntimeError("boom")), mock.patch(
            "knowledge.engine.metrics.record_archive"
        ) as record:
            process_archive_jobs(db)
        status, error = _rows(db)[0]
        assert status == "failed"
        assert "boom" in error
        record.assert_called_with(kind="source", status="failed")

    def test_source_dir_relativo(self, db: Path) -> None:
        payload = json.dumps({"source_dir": "relativa", "db_path": str(db)})
        _insert(db, "archive_source", "pending", payload)
        with mock.patch("knowledge.engine.archiver.archive_source") as archive:
            process_archive_jobs(db)
        assert _rows(db)[0][0] == "failed"
        archive.assert_not_called()

    def test_db_path_payload_relativo(self, db: Path) -> None:
        payload = json.dumps({"source_dir": "/tmp/abs", "db_path": "relativa"})
        _insert(db, "archive_source", "pending", payload)
        with mock.patch("knowledge.engine.archiver.archive_source") as archive:
            process_archive_jobs(db)
        assert _rows(db)[0][0] == "failed"
        archive.assert_not_called()

    def test_db_path_payload_distinto_absoluto(self, db: Path) -> None:
        payload = json.dumps({"source_dir": "/tmp/abs", "db_path": "/otra/base.sqlite"})
        _insert(db, "archive_source", "pending", payload)
        with mock.patch("knowledge.engine.archiver.archive_source") as archive:
            process_archive_jobs(db)
        archive.assert_called_once()
        assert _rows(db)[0][0] == "completed"

    def test_stale_recovery(self, db: Path) -> None:
        _insert(db, "archive_source", "running", "{}", started_at="2020-01-01 00:00:00")
        with mock.patch("knowledge.engine.metrics.record_archive"), mock.patch(
            "knowledge.engine.archiver.archive_source"
        ), mock.patch("knowledge.engine.metrics.job_retry_total") as retry:
            process_archive_jobs(db)
        retry.labels.assert_called_once_with(job_type="archive_source", reason="stale")

    def test_sin_jobs(self, db: Path) -> None:
        process_archive_jobs(db)  # no debe lanzar

    def test_error_global(self, db: Path) -> None:
        with mock.patch("knowledge.engine.jobs.open_db", side_effect=RuntimeError("boom")):
            process_archive_jobs(db)  # no debe lanzar

    def test_retry_metrics_falla_silencioso(self, db: Path) -> None:
        _insert(db, "archive_source", "running", "{}", started_at="2020-01-01 00:00:00")
        with mock.patch("knowledge.engine.metrics.record_archive"), mock.patch(
            "knowledge.engine.archiver.archive_source"
        ), mock.patch("knowledge.engine.metrics.job_retry_total") as retry:
            retry.labels.side_effect = RuntimeError("boom")
            process_archive_jobs(db)  # no debe lanzar


class TestCompileWorker:
    def test_compila_job(self, db: Path) -> None:
        _insert(db, "compile", "pending")
        result = SimpleNamespace(success=True, errors=())
        with mock.patch("knowledge.engine.compiler.compile_source", return_value=result), mock.patch(
            "knowledge.engine.lock.compile_lock", return_value=mock.MagicMock().__enter__()
        ):
            n = compile_worker(db, Path("/tmp/fuente"))
        assert n == 1
        assert _rows(db, "compile")[0][0] == "completed"

    def test_compila_falla(self, db: Path) -> None:
        _insert(db, "compile", "pending")
        result = SimpleNamespace(success=False, errors=(SimpleNamespace(message="err1"),))
        with mock.patch("knowledge.engine.compiler.compile_source", return_value=result), mock.patch(
            "knowledge.engine.lock.compile_lock", return_value=mock.MagicMock().__enter__()
        ):
            n = compile_worker(db, Path("/tmp/fuente"))
        assert n == 0
        status, error = _rows(db, "compile")[0]
        assert status == "failed"
        assert "err1" in error

    def test_lock_ocupado(self, db: Path) -> None:
        _insert(db, "compile", "pending")
        from knowledge.engine.lock import LockAcquisitionError

        with mock.patch("knowledge.engine.lock.compile_lock", side_effect=LockAcquisitionError("ocupado")):
            n = compile_worker(db, Path("/tmp/fuente"))
        assert n == 0
        assert _rows(db, "compile")[0][0] == "pending"

    def test_excepcion_inesperada(self, db: Path) -> None:
        _insert(db, "compile", "pending")
        with mock.patch("knowledge.engine.compiler.compile_source", side_effect=RuntimeError("boom")), mock.patch(
            "knowledge.engine.lock.compile_lock", return_value=mock.MagicMock().__enter__()
        ):
            n = compile_worker(db, Path("/tmp/fuente"))
        assert n == 0
        status, error = _rows(db, "compile")[0]
        assert status == "failed"
        assert "boom" in error

    def test_error_leyendo_jobs(self, db: Path) -> None:
        with mock.patch("knowledge.engine.jobs.open_db", side_effect=RuntimeError("boom")):
            assert compile_worker(db, Path("/tmp/fuente")) == 0

    def test_mark_done_error_silencioso(self, db: Path) -> None:
        _insert(db, "compile", "pending")
        result = SimpleNamespace(success=True, errors=())
        real_open_db = sqlite3.connect
        calls = {"n": 0}

        def fake_open_db(path):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("boom")
            conn = real_open_db(path)
            conn.row_factory = sqlite3.Row
            return conn

        with mock.patch("knowledge.engine.compiler.compile_source", return_value=result), mock.patch(
            "knowledge.engine.lock.compile_lock", return_value=mock.MagicMock().__enter__()
        ), mock.patch("knowledge.engine.jobs.open_db", side_effect=fake_open_db):
            assert compile_worker(db, Path("/tmp/fuente")) == 1

    def test_mark_failed_error_silencioso(self, db: Path) -> None:
        _insert(db, "compile", "pending")
        result = SimpleNamespace(success=False, errors=())
        calls = {"n": 0}
        real_open_db = sqlite3.connect

        def fake_open_db(path):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("boom")
            conn = real_open_db(path)
            conn.row_factory = sqlite3.Row
            return conn

        with mock.patch("knowledge.engine.compiler.compile_source", return_value=result), mock.patch(
            "knowledge.engine.lock.compile_lock", return_value=mock.MagicMock().__enter__()
        ), mock.patch("knowledge.engine.jobs.open_db", side_effect=fake_open_db):
            assert compile_worker(db, Path("/tmp/fuente")) == 0
