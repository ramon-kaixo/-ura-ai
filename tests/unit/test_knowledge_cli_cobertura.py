"""Tests de cobertura para knowledge/engine/cli/* (E2E vía main() con BD tmp)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import ClassVar

import pytest

from knowledge.engine.cli.main import (
    DEFAULT_DB_PATH,
    _get_conn,
    _resolve_db_path,
    build_parser,
    main,
)
from knowledge.engine.memory_store import MemoryRecord
from knowledge.engine.sqlite_writer import init_db

SCHEMA = Path("schemas/knowledge_graph.sql")


@pytest.fixture(autouse=True)
def _no_real_bus(monkeypatch) -> None:
    monkeypatch.setattr(
        "knowledge.engine.eventbus.get_bus",
        lambda: type("Bus", (), {"publish": lambda *a, **k: None})(),
    )
    monkeypatch.setattr("knowledge.engine.subscribers.subscribe_all", lambda *a, **k: None)


def _mk_db(tmp_path: Path, seed: bool = True) -> Path:
    import hashlib

    db = tmp_path / "k.db"
    init_db(db, SCHEMA)
    if seed:
        body1 = "Contenido de prueba"
        body2 = "Otro contenido"
        path1 = str(tmp_path / "docs" / "a.md")
        path2 = str(tmp_path / "docs" / "b.md")
        (tmp_path / "docs").mkdir(exist_ok=True)
        (tmp_path / "docs" / "a.md").write_text(body1)
        (tmp_path / "docs" / "b.md").write_text(body2)
        sha1 = hashlib.sha256(body1.encode("utf-8")).hexdigest()
        sha2 = hashlib.sha256(body2.encode("utf-8")).hexdigest()
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT OR REPLACE INTO kg_nodes (id, type, path, body, frontmatter, content_sha256, updated_at) "
            "VALUES ('n1', 'doc', ?, ?, '{\"title\": \"AAA\", \"tags\": []}', ?, '2026-08-01T00:00:00Z')",
            (path1, body1, sha1),
        )
        conn.execute("INSERT OR REPLACE INTO kg_nodes (id, type, path, body, frontmatter, content_sha256, updated_at) "
                     "VALUES ('n2', 'doc', ?, ?, '{}', ?, '2026-08-01T00:00:00Z')",
                     (path2, body2, sha2))
        conn.execute(
            "INSERT OR REPLACE INTO kg_edges (src, dst, relation, metadata) VALUES ('n1', 'n2', 'links', '{}')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO kg_nodes_fts (id, title, body, tags) "
            "VALUES ('n1', 'AAA', 'Contenido de prueba', '')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO kg_nodes_fts (id, title, body, tags) "
            "VALUES ('n2', '', 'Otro contenido', '')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO kg_active_version (singleton, graph_version, source_commit, compiler_version, swapped_at) "
            "VALUES (1, 3, 'HEAD', '0.1.0', '2026-08-01T00:00:00Z')"
        )
        conn.commit()
        conn.close()
        try:
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT OR REPLACE INTO op_assets (asset_id, asset_type, metadata, source, quality, created_at, updated_at) "
                "VALUES ('a1', 'markdown', '{\"title\": \"AAA\"}', '{}', 0.9, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')"
            )
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass
    return db


def _args(tmp_path: Path, *extra: str) -> list[str]:
    db = _mk_db(tmp_path)
    return ["ura-knowledge", "--db-path", str(db), *extra]


def _run(monkeypatch, capsys, argv: list[str]) -> int:
    monkeypatch.setattr("sys.argv", argv)
    return main()


# ── main.py: helpers ────────────────────────────────────────────────────────


def test_resolve_db_path(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    assert _resolve_db_path(SimpleNamespace(db_path=str(tmp_path / "x.db"))) == tmp_path / "x.db"
    monkeypatch.setenv("URA_KNOWLEDGE_DB", str(tmp_path / "env.db"))
    assert _resolve_db_path(SimpleNamespace(db_path="")) == tmp_path / "env.db"
    monkeypatch.delenv("URA_KNOWLEDGE_DB")
    assert _resolve_db_path(SimpleNamespace(db_path="")) == DEFAULT_DB_PATH


def test_get_conn(tmp_path) -> None:
    db = tmp_path / "conn.db"
    conn = _get_conn(db)
    assert conn is not None
    conn.close()
    assert db.parent.exists()


def test_add_command_y_build_parser() -> None:
    parser = build_parser()
    choices: list[str] = []
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            choices += list(action.choices)
    assert parser
    for name in (
        "init", "verify", "status", "compile", "doctor", "vacuum", "audit-db", "deduce",
        "compile-incremental", "search", "read", "related", "rules", "job-process", "pipeline",
        "agent", "feedback", "api", "archive", "docs", "notify", "metadata",
    ):
        assert name in choices


def test_parser_default_func(monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, ["ura-knowledge"]) == 1


# ── compile.py ──────────────────────────────────────────────────────────────


def test_cmd_init(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "init")) == 0
    assert (tmp_path / "k.db").exists()
    import knowledge.engine.cli.compile as c

    monkeypatch.setattr(c, "SCHEMA_FILE", tmp_path / "no-schema.sql")
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "k2.db"), "init"]) == 1


def test_cmd_verify(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "verify")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "verify", "--source-dir", str(tmp_path))) in (0, 1)


def test_cmd_status(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "status")) == 0
    out = capsys.readouterr().out
    assert "Graph version: 3" in out
    assert "Nodes: 2" in out
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "no.db"), "status"]) == 1


def test_cmd_compile(monkeypatch, capsys) -> None:
    calls = []

    def _fake_request(kind: str, **kw: object) -> int:
        calls.append((kind, kw))
        return 1


    monkeypatch.setattr("knowledge.engine.orchestrator.request_compile", _fake_request)
    monkeypatch.setattr("sys.argv", ["ura-knowledge", "--db-path", "/tmp/x.db", "compile"])
    assert main() == 0
    assert calls[0][0] == "cli"


def test_cmd_compile_incremental(monkeypatch, capsys) -> None:
    from types import SimpleNamespace

    import knowledge.engine.cli.compile as c
    from knowledge.engine.models import CompileResult

    ok = CompileResult(success=True, graph_version=1, source_commit="HEAD", compiler_version="1",
                       documents_total=0, documents_changed=0)
    monkeypatch.setattr("knowledge.engine.compiler.compile_incremental", lambda **kw: ok)
    args = SimpleNamespace(db_path="/tmp/inc.db", source_dir=None)
    assert c.cmd_compile_incremental(args) == 0
    args2 = SimpleNamespace(db_path="/tmp/inc.db", source_dir="src")
    assert c.cmd_compile_incremental(args2) == 0


# ── audit.py ────────────────────────────────────────────────────────────────


def test_cmd_vacuum(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "vacuum")) == 0
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "n.db"), "vacuum"]) == 1


def test_cmd_audit_db(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "audit-db")) == 0
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "n.db"), "audit-db"]) == 1


def test_cmd_audit_db_con_errores(tmp_path, monkeypatch, capsys) -> None:
    db = _mk_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("INSERT OR REPLACE INTO kg_edges (src, dst, relation, metadata) VALUES ('ghost', 'n1', 'x', '{}')")
    conn.commit()
    conn.close()
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(db), "audit-db"]) == 1


# ── search.py ───────────────────────────────────────────────────────────────


def test_cmd_read(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "read", "n1")) == 0
    out = capsys.readouterr().out
    assert "Contenido de prueba" in out
    assert _run(monkeypatch, capsys, _args(tmp_path, "read", "zzz")) == 1
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "no.db"), "read", "n1"]) == 1


def test_cmd_search(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "search", "contenido")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "search", "contenido", "--mode", "hybrid", "--type", "doc", "--limit", "2")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "search", "sinresultadosxyz")) == 0
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "no.db"), "search", "x"]) == 1
    out = capsys.readouterr().out
    assert "sinresultadosxyz" not in out


def test_cmd_related(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "related", "n1", "--relation", "links", "--depth", "2")) == 0
    out = capsys.readouterr().out
    assert "n1" in out
    assert _run(monkeypatch, capsys, _args(tmp_path, "related", "n2")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "related", "zzz")) in (0, 1)
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "no.db"), "related", "n1"]) == 1


# ── rules.py ────────────────────────────────────────────────────────────────


def test_cmd_rules_list(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "rules", "list")) == 0


def test_cmd_rules_eval(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "rules", "eval")) in (0, 1)
    assert _run(monkeypatch, capsys, _args(tmp_path, "rules", "eval", "n1")) in (0, 1)
    assert _run(monkeypatch, capsys, _args(tmp_path, "rules", "eval", "no-existe")) == 1
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "no.db"), "rules", "eval"]) == 1


def test_cmd_deduce(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "deduce")) == 0
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "no.db"), "deduce"]) == 1


# ── feedback.py ─────────────────────────────────────────────────────────────


def test_cmd_feedback(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "feedback", "rate", "123456789abc", "5")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "feedback", "rate", "123456789abc", "9")) == 1
    assert _run(monkeypatch, capsys, _args(tmp_path, "feedback", "rate", "zz", "4")) == 1
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "no.db"), "feedback", "rate", "123456789abc", "4"]) == 1
    assert _run(monkeypatch, capsys, _args(tmp_path, "feedback", "top", "--limit", "5")) == 0


# ── jobs.py / pipeline.py ───────────────────────────────────────────────────


def test_cmd_job_process(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr("knowledge.engine.orchestrator.compile_worker", lambda **kw: None)
    assert _run(monkeypatch, capsys, _args(tmp_path, "job-process")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "job-process", "--source-dir", str(tmp_path))) == 0


def test_cmd_pipeline_run(monkeypatch, capsys, tmp_path) -> None:
    class _Stage:
        error = "boom"

    class _Result:
        success = False
        stages: ClassVar[list[object]] = [_Stage()]  # type: ignore[assignment]

    class _Pipeline:
        def __init__(self, **kw: object):
            pass

        def run(self) -> _Result:
            return _Result()

    monkeypatch.setattr("knowledge.engine.cli.pipeline.Pipeline", _Pipeline)
    assert _run(monkeypatch, capsys, _args(tmp_path, "pipeline", "--source-dir", str(tmp_path))) == 1


def test_cmd_pipeline_ok(monkeypatch, capsys, tmp_path) -> None:
    class _Result:
        success = True
        stages: ClassVar[list[object]] = []

    class _Pipeline:
        def __init__(self, **kw: object):
            pass

        def run(self) -> _Result:
            return _Result()

    monkeypatch.setattr("knowledge.engine.cli.pipeline.Pipeline", _Pipeline)
    assert _run(monkeypatch, capsys, _args(tmp_path, "pipeline", "--archive-dir", str(tmp_path))) == 0


# ── agent.py ────────────────────────────────────────────────────────────────


def test_cmd_agent_list_y_run(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr("knowledge.engine.agent.list_agents", lambda: [])
    assert _run(monkeypatch, capsys, _args(tmp_path, "agent", "list")) == 0
    monkeypatch.setattr("knowledge.engine.agent.list_agents", lambda: ["buzo"])

    class _Agent:
        def __init__(self, *a: object, **k: object):
            pass

        def execute(self, goal: object) -> list:
            return []

    monkeypatch.setattr("knowledge.engine.agent.get_agent", lambda *a, **k: _Agent())
    monkeypatch.setattr("knowledge.engine.agent.AgentGoal", lambda **kw: object())
    assert _run(monkeypatch, capsys, _args(tmp_path, "agent", "list")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "agent", "run", "buzo")) == 0

    class _Finding:
        severity = "ERROR"
        title = "t"
        description = "d"

    class _Agent2(_Agent):
        def execute(self, goal: object) -> list:
            return [_Finding()]

    monkeypatch.setattr("knowledge.engine.agent.get_agent", lambda *a, **k: _Agent2())
    assert _run(monkeypatch, capsys, _args(tmp_path, "agent", "run", "buzo", "--kind", "coverage")) == 0
    monkeypatch.setattr("knowledge.engine.agent.get_agent", lambda *a, **k: None)
    assert _run(monkeypatch, capsys, _args(tmp_path, "agent", "run", "zzz")) == 1


# ── api.py ──────────────────────────────────────────────────────────────────


def test_cmd_api(monkeypatch, capsys, tmp_path) -> None:
    import os
    import sys

    calls = []

    def _fake_uvicorn(app: str, **kw: object) -> None:
        calls.append((app, kw))

    fake_uv = type("U", (), {"run": staticmethod(_fake_uvicorn)})()
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uv)
    monkeypatch.setattr("motor.core.secrets.get_secret", lambda name: "S3CRET")
    monkeypatch.delenv("URA_API_KEY", raising=False)
    assert _run(monkeypatch, capsys, _args(tmp_path, "api", "--port", "4097", "--host", "127.0.0.1", "--auth", "clave")) == 0
    assert calls[0][1]["port"] == 4097
    assert os.environ["URA_API_KEY"] == "clave"
    monkeypatch.setenv("URA_API_KEY", "env-key")
    assert _run(monkeypatch, capsys, _args(tmp_path, "api")) == 0
    assert calls[1][0] == "knowledge.engine.api:app"
    assert os.environ["URA_API_KEY"] == "env-key"
    monkeypatch.setattr("motor.core.secrets.get_secret", lambda name: None)
    assert _run(monkeypatch, capsys, _args(tmp_path, "api", "--host", "0.0.0.0")) == 0  # noqa: S104
    assert calls[2][1]["host"] == "0.0.0.0"  # noqa: S104


# ── archive.py ──────────────────────────────────────────────────────────────


def test_cmd_archive(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr("knowledge.engine.archiver.archive_source", lambda **kw: None)
    monkeypatch.setattr("knowledge.engine.archiver.list_archives", lambda archive_dir=None: [])
    monkeypatch.setattr("knowledge.engine.archiver.verify_archive", lambda m, archive_dir=None: True)
    monkeypatch.setattr("knowledge.engine.archiver.restore_source", lambda *a, **k: None)
    assert _run(monkeypatch, capsys, _args(tmp_path, "archive", "source", "--source-dir", str(tmp_path), "--retention-days", "30")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "archive", "list", "--archive-dir", str(tmp_path))) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "archive", "verify", "x.manifest.json", "--archive-dir", str(tmp_path))) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "archive", "restore", "x.manifest.json", "--dest", str(tmp_path))) == 0
    monkeypatch.setattr("knowledge.engine.archiver.list_archives", lambda archive_dir=None: [{"id": "x"}])
    assert _run(monkeypatch, capsys, _args(tmp_path, "archive", "list")) == 0
    monkeypatch.setattr("knowledge.engine.archiver.verify_archive", lambda m, archive_dir=None: False)
    assert _run(monkeypatch, capsys, _args(tmp_path, "archive", "verify", "y.json")) == 1


# ── docs.py / notify.py ─────────────────────────────────────────────────────


def test_cmd_docs_generate(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr("knowledge.engine.knowledge_base.generate_knowledge_base", lambda db, output_dir=None: 5)
    assert _run(monkeypatch, capsys, _args(tmp_path, "docs", "generate", "--output", str(tmp_path / "out"))) == 0
    monkeypatch.setattr("knowledge.engine.knowledge_base.generate_knowledge_base", lambda db, output_dir=None: 0)
    assert _run(monkeypatch, capsys, _args(tmp_path, "docs", "generate")) == 1


def test_cmd_notify(monkeypatch, capsys, tmp_path) -> None:
    import knowledge.engine.cli.notify as n

    class _Service:
        notifier_count = 0

        def add_notifier(self, x: object) -> None:
            self.notifier_count += 1

        def send(self, notification: object) -> int:
            return 1

    monkeypatch.setattr(n, "get_notifier", lambda: _Service())
    assert _run(monkeypatch, capsys, _args(tmp_path, "notify")) == 0

    service = _Service()
    monkeypatch.setattr(n, "get_notifier", lambda: service)
    assert _run(monkeypatch, capsys, _args(tmp_path, "notify", "--webhook", "https://x")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "notify", "--slack", "https://x")) == 0

    class _Failing(_Service):
        def send(self, notification: object) -> int:
            return 0

    monkeypatch.setattr(n, "get_notifier", lambda: _Failing())
    assert _run(monkeypatch, capsys, _args(tmp_path, "notify", "--webhook", "https://x")) == 1


# ── metadata.py ─────────────────────────────────────────────────────────────


def _seed_memory(db: Path) -> None:
    from knowledge.engine.memory_store import SQLiteMemoryStore

    store = SQLiteMemoryStore(db)
    store.save(MemoryRecord(memory_id="m1", kind="learning", title="Título", content="Contenido", tags=(), related_assets=()))


def test_cmd_metadata_lineage(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "metadata", "lineage", "a1")) == 0


def test_cmd_metadata_policy(tmp_path, monkeypatch, capsys) -> None:
    assert _run(monkeypatch, capsys, _args(tmp_path, "metadata", "policy", "a1")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "metadata", "policy")) == 0


def test_cmd_memory(tmp_path, monkeypatch, capsys) -> None:
    db = _mk_db(tmp_path)
    _seed_memory(db)
    argv = ["ura-knowledge", "--db-path", str(db)]
    assert _run(monkeypatch, capsys, [*argv, "metadata", "memory", "create", "learning", "Título", "Contenido", "--tags", "a,b"]) == 0
    assert _run(monkeypatch, capsys, [*argv, "metadata", "memory", "list", "--limit", "10"]) == 0
    assert _run(monkeypatch, capsys, [*argv, "metadata", "memory", "show", "m1"]) == 0
    assert _run(monkeypatch, capsys, [*argv, "metadata", "memory", "search", "título"]) == 0
    assert _run(monkeypatch, capsys, [*argv, "metadata", "memory", "link", "m1", "a1"]) in (0, 1)


def test_cmd_metadata_retrieve_context(tmp_path, monkeypatch, capsys) -> None:
    class _Bundle:
        assets: ClassVar[list[object]] = []
        memories: ClassVar[list[object]] = []

        def to_dict(self) -> dict:
            return {"query": "q", "stats": {}}

    class _Retriever:
        def build_context(self, **kw: object) -> _Bundle:
            return _Bundle()

        def retrieve_assets(self, **kw: object) -> list:
            return []

    monkeypatch.setattr("knowledge.engine.graphrag.SQLiteGraphRetriever", lambda db: _Retriever())
    assert _run(monkeypatch, capsys, _args(tmp_path, "metadata", "retrieve", "consulta")) == 0
    assert _run(monkeypatch, capsys, _args(tmp_path, "metadata", "context", "consulta")) == 0


# ── doctor.py ───────────────────────────────────────────────────────────────


def test_cmd_doctor(tmp_path, monkeypatch, capsys) -> None:
    db = _mk_db(tmp_path)
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(db), "doctor"]) == 0
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO op_vector_sync (doc_id, operation, status, created_at) "
                 "VALUES ('n1', 'upsert', 'dead_letter', '2026-08-01T00:00:00Z')")
    conn.commit()
    conn.close()
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(db), "doctor"]) == 1
    assert _run(monkeypatch, capsys, ["ura-knowledge", "--db-path", str(tmp_path / "no.db"), "doctor"]) == 1
