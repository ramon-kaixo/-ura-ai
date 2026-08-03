"""Tests para knowledge/engine/cli/doctor.py — health check."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from knowledge.engine.cli.doctor import cmd_doctor


def _crear_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE op_vector_sync (status TEXT)")
    conn.execute("CREATE TABLE kg_nodes (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT)")
    conn.commit()
    conn.close()


class TestCmdDoctor:
    def test_db_no_existe(self, tmp_path) -> None:
        args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"))
        assert cmd_doctor(args) == 1

    def test_db_sana(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        with mock.patch("knowledge.engine.cli.doctor.get_schema_version", return_value=1):
            with mock.patch("knowledge.engine.cli.doctor.SCHEMA_VERSION", 1):
                with mock.patch("knowledge.engine.cli.doctor.verify_graph", return_value=[]):
                    with mock.patch("knowledge.engine.cli.doctor.check_fts_sync", return_value=[]):
                        with mock.patch("knowledge.engine.cli.doctor.get_pending_delete_ids", return_value=[]):
                            with mock.patch("knowledge.engine.cli.doctor._get_qdrant", return_value=mock.Mock()):
                                args = SimpleNamespace(db_path=str(db))
                                assert cmd_doctor(args) == 0

    def test_schema_version_desactualizada(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        with mock.patch("knowledge.engine.migrations.get_schema_version", return_value=0):
            with mock.patch("knowledge.engine.cli.doctor.SCHEMA_VERSION", 1):
                with mock.patch("knowledge.engine.cli.doctor.verify_graph", return_value=[]):
                    with mock.patch("knowledge.engine.cli.doctor.check_fts_sync", return_value=[]):
                        with mock.patch("knowledge.engine.cli.doctor.get_pending_delete_ids", return_value=[]):
                            with mock.patch("knowledge.engine.cli.doctor._get_qdrant", return_value=mock.Mock()):
                                args = SimpleNamespace(db_path=str(db))
                                assert cmd_doctor(args) == 1  # FAIL schema

    def test_grafos_con_error(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        with mock.patch("knowledge.engine.cli.doctor.get_schema_version", return_value=1):
            with mock.patch("knowledge.engine.cli.doctor.SCHEMA_VERSION", 1):
                with mock.patch("knowledge.engine.cli.doctor.verify_graph", return_value=[("ERROR", "n", "x")]):
                    with mock.patch("knowledge.engine.cli.doctor.check_fts_sync", return_value=[]):
                        with mock.patch("knowledge.engine.cli.doctor.get_pending_delete_ids", return_value=[]):
                            with mock.patch("knowledge.engine.cli.doctor._get_qdrant", return_value=mock.Mock()):
                                args = SimpleNamespace(db_path=str(db))
                                assert cmd_doctor(args) == 1  # FAIL graph

    def test_qdrant_no_disponible(self, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        _crear_db(db)
        with mock.patch("knowledge.engine.cli.doctor.get_schema_version", return_value=1):
            with mock.patch("knowledge.engine.cli.doctor.SCHEMA_VERSION", 1):
                with mock.patch("knowledge.engine.cli.doctor.verify_graph", return_value=[]):
                    with mock.patch("knowledge.engine.cli.doctor.check_fts_sync", return_value=[]):
                        with mock.patch("knowledge.engine.cli.doctor.get_pending_delete_ids", return_value=[]):
                            with mock.patch("knowledge.engine.cli.doctor._get_qdrant", return_value=None):
                                args = SimpleNamespace(db_path=str(db))
                                assert cmd_doctor(args) == 0  # WARN no falla
