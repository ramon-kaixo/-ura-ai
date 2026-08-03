"""Tests para knowledge/engine/cli/ — __main__, rules y compile."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest


def _crear_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE kg_nodes (id TEXT PRIMARY KEY, type TEXT, path TEXT, frontmatter TEXT, body TEXT)")
    conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT, relation TEXT)")
    conn.execute("CREATE TABLE kg_active_version (singleton INTEGER, graph_version TEXT, source_commit TEXT, compiler_version TEXT, swapped_at TEXT)")
    conn.execute("CREATE TABLE op_compile_errors (severity TEXT)")
    conn.execute("INSERT INTO kg_active_version VALUES (1, 'v1', 'abc', 'c1', 'now')")
    conn.commit()
    conn.close()


class TestMainModule:
    def test_import_main(self, monkeypatch) -> None:
        import importlib
        import sys as _sys

        # El modulo __main__ ejecuta main() + sys.exit al importarse
        main_mock = mock.Mock(return_value=0)
        import importlib as _il
        import sys as _sys_mod

        _il.import_module("knowledge.engine.cli.main")
        cli_main_mod = _sys_mod.modules["knowledge.engine.cli.main"]
        monkeypatch.setattr(cli_main_mod, "main", main_mock)
        with mock.patch("sys.argv", ["__main__.py"]):
            with pytest.raises(SystemExit) as e:
                importlib.reload(importlib.import_module("knowledge.engine.cli.__main__"))
        assert e.value.code == 0
        main_mock.assert_called_once()


class TestCmdRulesList:
    def test_vacio(self, monkeypatch) -> None:
        from knowledge.engine.cli.rules import cmd_rules_list

        monkeypatch.setattr("knowledge.engine.rules.list_rules", mock.Mock(return_value=[]))
        assert cmd_rules_list(SimpleNamespace()) == 0

    def test_con_reglas(self, monkeypatch) -> None:
        from knowledge.engine.cli.rules import cmd_rules_list

        regla = mock.Mock()
        regla.metadata.severity = "WARN"
        monkeypatch.setattr("knowledge.engine.rules.list_rules", mock.Mock(return_value=[regla, regla]))
        assert cmd_rules_list(SimpleNamespace()) == 0


class TestCmdRulesEval:
    def test_db_no_existe(self, tmp_path) -> None:
        from knowledge.engine.cli.rules import cmd_rules_eval

        args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"))
        assert cmd_rules_eval(args) == 1

    def test_ok_sin_resultados(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.rules import cmd_rules_eval

        db = tmp_path / "db.sqlite"
        _crear_db(db)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO kg_nodes VALUES ('n1', 'doc', 'p1.md', '{\"title\": \"T\"}', 'cuerpo')")
        conn.commit()
        conn.close()
        evaluator = mock.Mock()
        evaluator.evaluate.return_value = []
        monkeypatch.setattr("knowledge.engine.rules.RuleEvaluator", mock.Mock(return_value=evaluator))
        args = SimpleNamespace(db_path=str(db))
        assert cmd_rules_eval(args) == 0

    def test_con_resultados_error(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.rules import cmd_rules_eval

        db = tmp_path / "db.sqlite"
        _crear_db(db)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO kg_nodes VALUES ('n1', 'doc', 'p1.md', NULL, 'cuerpo')")
        conn.commit()
        conn.close()
        evaluator = mock.Mock()
        r = mock.Mock()
        r.severity = "ERROR"
        evaluator.evaluate.return_value = [r]
        monkeypatch.setattr("knowledge.engine.rules.RuleEvaluator", mock.Mock(return_value=evaluator))
        args = SimpleNamespace(db_path=str(db))
        assert cmd_rules_eval(args) == 1

    def test_filter_doc_no_encontrado(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.rules import cmd_rules_eval

        db = tmp_path / "db.sqlite"
        _crear_db(db)
        args = SimpleNamespace(db_path=str(db), doc_id="noexiste")
        assert cmd_rules_eval(args) == 1


class TestCmdDeduce:
    def test_db_no_existe(self, tmp_path) -> None:
        from knowledge.engine.cli.rules import cmd_deduce

        args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"))
        assert cmd_deduce(args) == 1

    def test_ok(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.rules import cmd_deduce

        db = tmp_path / "db.sqlite"
        _crear_db(db)
        deductor = mock.Mock()
        deductor.deduce.return_value = [mock.Mock()]
        monkeypatch.setattr("knowledge.engine.deduction.StateDeductor", mock.Mock(return_value=deductor))
        args = SimpleNamespace(db_path=str(db))
        assert cmd_deduce(args) == 0

    def test_sin_deducciones(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.rules import cmd_deduce

        db = tmp_path / "db.sqlite"
        _crear_db(db)
        deductor = mock.Mock()
        deductor.deduce.return_value = []
        monkeypatch.setattr("knowledge.engine.deduction.StateDeductor", mock.Mock(return_value=deductor))
        args = SimpleNamespace(db_path=str(db))
        assert cmd_deduce(args) == 0


class TestCmdInit:
    def test_schema_no_existe(self, tmp_path, monkeypatch) -> None:
        from knowledge.engine.cli.compile import cmd_init

        monkeypatch.setattr("knowledge.engine.cli.compile.SCHEMA_FILE", tmp_path / "nope.sql")
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"))
        assert cmd_init(args) == 1

    def test_ok(self, tmp_path, monkeypatch) -> None:
        from knowledge.engine.cli.compile import cmd_init

        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE x (id INTEGER);")
        monkeypatch.setattr("knowledge.engine.cli.compile.SCHEMA_FILE", schema)
        init = mock.Mock()
        monkeypatch.setattr("knowledge.engine.cli.compile.init_db", init)
        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"))
            assert cmd_init(args) == 0
        init.assert_called_once()


class TestCmdVerify:
    def test_sin_resultados(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.compile import cmd_verify

        monkeypatch.setattr("knowledge.engine.cli.compile.verify_graph", mock.Mock(return_value=[]))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"))
        assert cmd_verify(args) == 1

    def test_con_errores(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.compile import cmd_verify

        results = [("ERROR", "check1", "msg"), ("WARN", "check2", "msg"), ("INFO", "check3", "msg")]
        monkeypatch.setattr("knowledge.engine.cli.compile.verify_graph", mock.Mock(return_value=results))
        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"))
            assert cmd_verify(args) == 1

    def test_ok(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.compile import cmd_verify

        monkeypatch.setattr("knowledge.engine.cli.compile.verify_graph", mock.Mock(return_value=[("INFO", "c", "m")]))
        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"))
            assert cmd_verify(args) == 0


class TestCmdStatus:
    def test_db_no_existe(self, tmp_path) -> None:
        from knowledge.engine.cli.compile import cmd_status

        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"))
            assert cmd_status(args) == 1

    def test_ok(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.compile import cmd_status

        db = tmp_path / "db.sqlite"
        _crear_db(db)
        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(db))
            assert cmd_status(args) == 0


class TestCmdCompile:
    def test_incremental_ok(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.compile import cmd_compile_incremental

        result = mock.Mock()
        result.success = True
        result.documents_changed = 2
        monkeypatch.setattr("knowledge.engine.compiler.compile_incremental", mock.Mock(return_value=result))
        args = SimpleNamespace(source_dir=str(tmp_path / "src"), db_path=str(tmp_path / "db.sqlite"))
        assert cmd_compile_incremental(args) == 0

    def test_incremental_fail(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.compile import cmd_compile_incremental

        result = mock.Mock()
        result.success = False
        result.documents_changed = 0
        monkeypatch.setattr("knowledge.engine.compiler.compile_incremental", mock.Mock(return_value=result))
        args = SimpleNamespace(source_dir=str(tmp_path / "src"), db_path=str(tmp_path / "db.sqlite"))
        assert cmd_compile_incremental(args) == 1

    def test_compile_ok(self, monkeypatch, tmp_path) -> None:
        from knowledge.engine.cli.compile import cmd_compile

        monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", mock.Mock(return_value=5))
        args = SimpleNamespace(source_dir=None, db_path=str(tmp_path / "db.sqlite"))
        assert cmd_compile(args) == 0
