"""Tests para knowledge/engine/verifier.py y knowledge/engine/cli/main.py."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from knowledge.engine.cli.main import _resolve_db_path, add_parser_init, add_parser_status, add_parser_verify, main
from knowledge.engine.verifier import _safe_check, verify_graph


class TestSafeCheck:
    def test_ok(self) -> None:
        out = _safe_check("WARN", "check1", lambda conn: ["m1", "m2"], None)
        assert out == [("WARN", "check1", "m1"), ("WARN", "check1", "m2")]

    def test_sin_mensajes(self) -> None:
        assert _safe_check("ERROR", "check1", lambda conn: [], None) == []

    def test_operational_error(self) -> None:
        def boom(conn):
            raise sqlite3.OperationalError("no table")

        out = _safe_check("ERROR", "check1", boom, None)
        assert len(out) == 1
        assert out[0][0] == "ERROR"
        assert "no accesible" in out[0][2]

    def test_oserror(self) -> None:
        def boom(conn):
            raise OSError("disk")

        out = _safe_check("WARN", "c", boom, None)
        assert "no accesible" in out[0][2]


class TestVerifyGraph:
    def _crear_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE kg_nodes (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT)")
        conn.execute("CREATE TABLE op_compile_errors (error_code TEXT, severity TEXT, message TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE kg_active_version (singleton INTEGER, graph_version TEXT, source_commit TEXT, compiler_version TEXT, swapped_at TEXT)")
        conn.execute("INSERT INTO kg_active_version VALUES (1, 'v1', 'abc123def456', 'c1', 'now')")
        conn.commit()
        return conn

    def test_db_no_existe(self, tmp_path) -> None:
        out = verify_graph(tmp_path / "nope.sqlite")
        assert out == [("ERROR", "db_exists", "knowledge.db no existe")]

    def test_db_sana(self, tmp_path, monkeypatch) -> None:
        db = tmp_path / "db.sqlite"
        conn = self._crear_db(db)
        conn.close()
        for name in ["check_pragmas", "check_schema", "check_fts_sync", "check_duplicate_ids", "check_duplicate_paths", "check_repeated_hashes", "check_referential_integrity", "check_orphans", "check_cycles", "check_ontology"]:
            monkeypatch.setattr(f"knowledge.engine.verifier.{name}", mock.Mock(return_value=[]))
        monkeypatch.setattr("knowledge.engine.verifier.verify_hashes", mock.Mock(return_value=[]))
        monkeypatch.setattr("knowledge.engine.verifier.get_schema_version", mock.Mock(return_value=1))
        monkeypatch.setattr("knowledge.engine.verifier.SCHEMA_VERSION", 1)
        out = verify_graph(db)
        severities = [s for s, _, _ in out]
        assert "INFO" in severities
        assert "ERROR" not in severities

    def test_schema_mismatch(self, tmp_path, monkeypatch) -> None:
        db = tmp_path / "db.sqlite"
        conn = self._crear_db(db)
        conn.close()
        monkeypatch.setattr("knowledge.engine.migrations.get_schema_version", mock.Mock(return_value=0))
        monkeypatch.setattr("knowledge.engine.verifier.SCHEMA_VERSION", 1)
        for name in ["check_pragmas", "check_schema", "check_fts_sync", "check_duplicate_ids", "check_duplicate_paths", "check_repeated_hashes", "check_referential_integrity", "check_orphans", "check_cycles", "check_ontology"]:
            monkeypatch.setattr(f"knowledge.engine.verifier.{name}", mock.Mock(return_value=[]))
        monkeypatch.setattr("knowledge.engine.verifier.verify_hashes", mock.Mock(return_value=[]))
        out = verify_graph(db)
        assert any(s == "ERROR" and c == "schema_version" for s, c, _ in out)

    def test_check_con_error(self, tmp_path, monkeypatch) -> None:
        db = tmp_path / "db.sqlite"
        conn = self._crear_db(db)
        conn.close()
        monkeypatch.setattr("knowledge.engine.verifier.get_schema_version", mock.Mock(return_value=1))
        monkeypatch.setattr("knowledge.engine.verifier.SCHEMA_VERSION", 1)
        for name in ["check_pragmas", "check_schema", "check_fts_sync", "check_duplicate_ids", "check_duplicate_paths", "check_repeated_hashes", "check_referential_integrity", "check_orphans", "check_cycles", "check_ontology"]:
            monkeypatch.setattr(f"knowledge.engine.verifier.{name}", mock.Mock(return_value=[]))
        monkeypatch.setattr("knowledge.engine.verifier.verify_hashes", mock.Mock(return_value=["hash roto"]))
        out = verify_graph(db)
        assert any(c == "hashes" for _, c, _ in out)

    def test_sin_version(self, tmp_path, monkeypatch) -> None:
        db = tmp_path / "db.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE kg_nodes (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT)")
        conn.execute("CREATE TABLE op_compile_errors (error_code TEXT, severity TEXT, message TEXT, created_at TEXT)")
        conn.commit()
        conn.close()
        monkeypatch.setattr("knowledge.engine.verifier.get_schema_version", mock.Mock(return_value=1))
        monkeypatch.setattr("knowledge.engine.verifier.SCHEMA_VERSION", 1)
        for name in ["check_pragmas", "check_schema", "check_fts_sync", "check_duplicate_ids", "check_duplicate_paths", "check_repeated_hashes", "check_referential_integrity", "check_orphans", "check_cycles", "check_ontology"]:
            monkeypatch.setattr(f"knowledge.engine.verifier.{name}", mock.Mock(return_value=[]))
        monkeypatch.setattr("knowledge.engine.verifier.verify_hashes", mock.Mock(return_value=[]))
        out = verify_graph(db)
        assert any("Sin versión activa" in m for _, _, m in out)


class TestCliMainHelpers:
    def test_resolve_db_path_arg(self) -> None:
        args = SimpleNamespace(db_path="/tmp/x.sqlite")
        assert _resolve_db_path(args) == Path("/tmp/x.sqlite")

    def test_resolve_db_path_env(self, monkeypatch) -> None:
        monkeypatch.setenv("URA_KNOWLEDGE_DB", "/tmp/env.sqlite")
        args = SimpleNamespace(db_path=None)
        assert _resolve_db_path(args) == Path("/tmp/env.sqlite")

    def test_resolve_db_path_default(self, monkeypatch) -> None:
        monkeypatch.delenv("URA_KNOWLEDGE_DB", raising=False)
        args = SimpleNamespace(db_path=None)
        out = _resolve_db_path(args)
        assert "knowledge.db" in str(out)

    def test_parsers_requieren_cmd_funciones(self) -> None:
        """BUG REAL del otro agente: cli/main.py referencia cmd_init,
        cmd_verify, cmd_status y build_parser que NO estan definidos en
        el modulo. El CLI de knowledge no es invocable tal cual."""
        import sys as _sys

        m = _sys.modules["knowledge.engine.cli.main"]
        for attr in ("cmd_init", "cmd_verify", "cmd_status", "build_parser"):
            assert not hasattr(m, attr), f"{attr} deberia faltar (bug documentado)"

    def test_main_init_bus(self, monkeypatch) -> None:
        bus = mock.Mock()
        monkeypatch.setattr("knowledge.engine.eventbus.get_bus", mock.Mock(return_value=bus))
        subscribe = mock.Mock()
        monkeypatch.setattr("knowledge.engine.subscribers.subscribe_all", subscribe)
        from knowledge.engine.cli.main import _init_bus

        monkeypatch.delenv("URA_KNOWLEDGE_DB", raising=False)
        _init_bus()
        subscribe.assert_called_once()
