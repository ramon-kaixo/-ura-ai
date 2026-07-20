"""CLI: init, verify, status, compile."""

from pathlib import Path

from knowledge.engine.cli.main import SCHEMA_FILE, _get_conn, _resolve_db_path
from knowledge.engine.sqlite_writer import init_db
from knowledge.engine.verifier import verify_graph


def cmd_init(args) -> int:
    db_path = _resolve_db_path(args)
    if not SCHEMA_FILE.exists():
        return 1
    init_db(db_path, SCHEMA_FILE)
    return 0


def cmd_verify(args) -> int:
    db_path = _resolve_db_path(args)
    source_dir = getattr(args, "source_dir", None)
    if source_dir:
        source_dir = Path(source_dir)
    results = verify_graph(db_path, source_dir=source_dir)
    if not results:
        return 1
    errors = 0
    warnings = 0
    for severity, _check, _msg in results:
        {"ERROR": "\u274c", "WARN": "\u26a0\ufe0f", "INFO": "[i]"}.get(severity, "?")
        if severity == "ERROR":
            errors += 1
        elif severity == "WARN":
            warnings += 1
    if errors == 0 and warnings == 0:
        pass
    else:
        pass
    return 1 if errors > 0 else 0


def cmd_status(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        return 1
    conn = _get_conn(db_path)
    try:
        version = conn.execute(
            "SELECT graph_version, source_commit, compiler_version, swapped_at FROM kg_active_version WHERE singleton=1",
        ).fetchone()
        conn.execute("SELECT COUNT(*) as c FROM kg_nodes").fetchone()["c"]
        conn.execute("SELECT COUNT(*) as c FROM kg_edges").fetchone()["c"]
        conn.execute("SELECT COUNT(*) as c FROM op_compile_errors WHERE severity='ERROR'").fetchone()["c"]
    finally:
        conn.close()
    if version:
        pass
    else:
        pass
    return 0


def cmd_compile_incremental(args) -> int:
    """Compilación incremental: solo docs modificados."""
    db_path = _resolve_db_path(args)
    source_dir = Path(args.source_dir).resolve() if hasattr(args, "source_dir") and args.source_dir else None
    from knowledge.engine.compiler import compile_incremental

    result = compile_incremental(source_dir=source_dir, db_path=db_path)
    if result.documents_changed == 0 and result.success:
        return 0
    return 0 if result.success else 1


def cmd_compile(args) -> int:
    db_path = _resolve_db_path(args)
    source_dir = Path(args.source_dir).resolve() if hasattr(args, "source_dir") and args.source_dir else None
    from knowledge.engine.orchestrator import request_compile

    n = request_compile("cli", source_dir=source_dir, db_path=db_path)
    if n:
        return 0
    return 0
