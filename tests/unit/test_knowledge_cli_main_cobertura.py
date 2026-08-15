"""Cobertura 100x100 de knowledge/engine/cli/main.py (TASK-20260815-003).

Cubre build_parser (árbol completo de subcomandos), _resolve_db_path,
_add_command y helpers, con los módulos CLI reales (que importan bien).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from knowledge.engine.cli.main import (
    DEFAULT_DB_PATH,
    SCHEMA_FILE,
    _add_agent,
    _add_api,
    _add_archive,
    _add_basic,
    _add_command,
    _add_docs_notify,
    _add_feedback,
    _add_memory,
    _add_metadata,
    _add_pipeline_jobs,
    _add_rules,
    _add_search,
    _get_conn,
    _init_bus,
    _resolve_db_path,
    build_parser,
)


def _subparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    return p.add_subparsers()


class TestResolveDbPath:
    def test_por_args(self) -> None:
        args = argparse.Namespace(db_path="/tmp/x.db")
        assert _resolve_db_path(args) == Path("/tmp/x.db")

    def test_sin_db_path_usa_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_KNOWLEDGE_DB", "/env/db.sqlite")
        assert _resolve_db_path(argparse.Namespace(db_path="")) == Path("/env/db.sqlite")

    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("URA_KNOWLEDGE_DB", raising=False)
        assert _resolve_db_path(argparse.Namespace(db_path="")) == DEFAULT_DB_PATH

    def test_default_sin_env_existe(self) -> None:
        assert str(DEFAULT_DB_PATH).endswith("knowledge.db")
        assert SCHEMA_FILE.name == "knowledge_graph.sql"


class TestGetConn:
    def test_crea_conexion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("knowledge.engine.connection.open_db", lambda p: ("conn", p))
        db = tmp_path / "sub" / "db.sqlite"
        conn = _get_conn(db)
        assert conn == ("conn", db)
        assert db.parent.exists()


class TestAddCommand:
    def test_registra_subcomando(self) -> None:
        sub = _subparser()

        def func(args: argparse.Namespace) -> int:
            return 7

        p = _add_command(sub, "hola", func, "help text")
        assert p.get_default("func") is func
        assert p.prog.endswith("hola")


class TestBuildParser:
    def test_arbol_completo(self) -> None:
        parser = build_parser()
        # subparsers registrados
        names = set(parser._subparsers._group_actions[0].choices.keys())
        esperados = {
            "init", "verify", "status", "compile", "doctor", "vacuum", "audit-db",
            "deduce", "compile-incremental", "search", "read", "related", "rules",
            "job-process", "pipeline", "agent", "feedback", "api", "archive",
            "docs", "notify", "metadata",
        }
        assert esperados <= names

    def test_parser_help_no_falla(self) -> None:
        parser = build_parser()
        parser.print_help()

    def test_default_func(self) -> None:
        parser = build_parser()
        assert callable(parser.get_default("func"))

    def test_parse_search(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["search", "query", "--mode", "hybrid", "--limit", "5"])
        assert args.query == "query"
        assert args.mode == "hybrid"
        assert args.limit == 5

    def test_parse_rules_list(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["rules", "list"])
        assert args.rules_cmd == "list"
        assert callable(args.func)

    def test_parse_agent_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["agent", "run", "a1", "--kind", "coverage"])
        assert args.agent_id == "a1"
        assert args.kind == "coverage"

    def test_parse_feedback_rate(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["feedback", "rate", "doc1", "5"])
        assert args.doc_id == "doc1"
        assert args.rating == 5

    def test_parse_archive_list(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["archive", "list"])
        assert args.archive_cmd == "list"

    def test_parse_metadata_lineage(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["metadata", "lineage", "asset1"])
        assert args.metadata_cmd == "lineage"
        assert args.asset_id == "asset1"

    def test_parse_memory_create(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["metadata", "memory", "create", "note", "titulo", "contenido"])
        assert args.memory_cmd == "create"
        assert args.kind == "note"

    def test_parse_docs_generate(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["docs", "generate", "--output", "/tmp/out"])
        assert args.docs_cmd == "generate"
        assert args.output == "/tmp/out"

    def test_parse_api(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["api", "--port", "5000"])
        assert args.port == 5000

    def test_parse_verify_source_dir(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["verify", "--source-dir", "/src"])
        assert args.source_dir == "/src"

    def test_parse_pipeline(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pipeline", "--source-dir", "/s", "--archive-dir", "/a"])
        assert args.source_dir == "/s"
        assert args.archive_dir == "/a"

    def test_parse_compile_incremental(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["compile-incremental", "--source-dir", "/s"])
        assert args.source_dir == "/s"

    def test_parse_read(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["read", "doc_1"])
        assert args.doc_id == "doc_1"

    def test_parse_related_depth(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["related", "doc_1", "--depth", "3"])
        assert args.depth == 3


class TestMain:
    def test_main_llama_func(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        import knowledge.engine.cli.main as main_mod
        # el paquete cli/__init__ pisa el atributo main con la funcion;
        # sys.modules tiene el modulo real
        main_mod = sys.modules["knowledge.engine.cli.main"]

        llamado = {}

        def fake_func(args: argparse.Namespace) -> int:
            llamado["args"] = args
            return 42

        class FakeParser:
            def parse_args(self) -> argparse.Namespace:
                return argparse.Namespace(func=fake_func)

        monkeypatch.setattr(main_mod, "_init_bus", lambda: None)
        monkeypatch.setattr(main_mod, "build_parser", lambda: FakeParser())
        assert main_mod.main() == 42
        assert llamado["args"] is not None

    def test_init_bus(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bus = object()

        class FakeBus:
            def publish(self, *a: object, **k: object) -> None:
                return None

        monkeypatch.setattr("knowledge.engine.eventbus.get_bus", lambda: FakeBus())
        monkeypatch.setattr("knowledge.engine.subscribers.subscribe_all", lambda *a, **k: None)
        _init_bus()  # no debe lanzar

    def test_init_bus_con_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("URA_KNOWLEDGE_DB", "/tmp/env.db")
        monkeypatch.setattr("knowledge.engine.eventbus.get_bus", lambda: object())
        monkeypatch.setattr("knowledge.engine.subscribers.subscribe_all", lambda *a, **k: None)
        _init_bus()


class TestMainExec:
    def test_main_block(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        import knowledge.engine.cli.main as main_mod
        main_mod = sys.modules["knowledge.engine.cli.main"]

        def fake_main() -> int:
            return 0

        monkeypatch.setattr(main_mod, "main", fake_main)
        monkeypatch.setattr(main_mod.sys, "exit", lambda code: None)
        monkeypatch.setattr(main_mod, "__name__", "__main__")
        # ejecutar el bloque if __name__ == "__main__"
        code = compile(open(main_mod.__file__).read(), main_mod.__file__, "exec")
        exec(code, main_mod.__dict__)
