"""Tests para knowledge/engine/cli/audit.py — vacuum y audit_db."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from knowledge.engine.cli.audit import cmd_audit_db, cmd_vacuum


def _crear_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE kg_nodes (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT)")
    conn.execute("CREATE TABLE kg_active_version (id INTEGER)")
    conn.execute("CREATE TABLE op_jobs (status TEXT, started_at TEXT)")
    conn.execute("CREATE TABLE op_vector_sync (status TEXT)")
    conn.execute("INSERT INTO kg_active_version VALUES (1)")
    conn.commit()
    conn.close()


class TestCmdVacuum:
    def test_db_no_existe(self, tmp_path) -> None:
        args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"))
        assert cmd_vacuum(args) == 1

    def test_vacuum_ok(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        args = SimpleNamespace(db_path=str(db))
        assert cmd_vacuum(args) == 0


class TestCmdAuditDb:
    def test_db_no_existe(self, tmp_path) -> None:
        args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"))
        assert cmd_audit_db(args) == 1

    def test_db_sana(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        args = SimpleNamespace(db_path=str(db))
        assert cmd_audit_db(args) == 0

    def test_audit_backend_ok(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        audit = mock.Mock()
        audit.backend = mock.Mock()
        health = mock.Mock()
        health.healthy = True
        health.events_written = 42
        health.error = ""
        audit.backend.health_check.return_value = health
        mock.Mock()
        args = SimpleNamespace(db_path=str(db))
        with mock.patch("knowledge.engine.audit.get_audit", return_value=audit):
            assert cmd_audit_db(args) == 0

    def test_audit_backend_fail(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        audit = mock.Mock()
        audit.backend = mock.Mock()
        health = mock.Mock()
        health.healthy = False
        health.events_written = 0
        health.error = "corrupto"
        audit.backend.health_check.return_value = health
        args = SimpleNamespace(db_path=str(db))
        with mock.patch("knowledge.engine.audit.get_audit", return_value=audit):
            assert cmd_audit_db(args) == 1  # FAIL audit -> errors

    def test_orhpan_edges(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO kg_edges VALUES ('nope', 'n2')")
        conn.commit()
        conn.close()
        args = SimpleNamespace(db_path=str(db))
        assert cmd_audit_db(args) == 1  # FAIL orphan

    def test_multiples_versiones(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO kg_active_version VALUES (2)")
        conn.commit()
        conn.close()
        args = SimpleNamespace(db_path=str(db))
        assert cmd_audit_db(args) == 1  # FAIL active_version
