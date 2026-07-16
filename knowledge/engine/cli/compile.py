"""CLI: init, verify, status, compile."""

from pathlib import Path

from knowledge.engine.cli.main import SCHEMA_FILE, _get_conn, _resolve_db_path
from knowledge.engine.migrations import SCHEMA_VERSION
from knowledge.engine.sqlite_writer import init_db
from knowledge.engine.verifier import verify_graph


def cmd_init(args) -> int:
    db_path = _resolve_db_path(args)
    if not SCHEMA_FILE.exists():
        print(f"Error: schema file not found: {SCHEMA_FILE}")
        return 1
    init_db(db_path, SCHEMA_FILE)
    print(f"Knowledge DB initialized (schema v{SCHEMA_VERSION}): {db_path}")
    return 0


def cmd_verify(args) -> int:
    db_path = _resolve_db_path(args)
    source_dir = getattr(args, "source_dir", None)
    if source_dir:
        source_dir = Path(source_dir)
    results = verify_graph(db_path, source_dir=source_dir)
    if not results:
        print("Knowledge DB does not exist.")
        return 1
    errors = 0
    warnings = 0
    for severity, check, msg in results:
        prefix = {"ERROR": "\u274c", "WARN": "\u26a0\ufe0f", "INFO": "[i]"}.get(severity, "?")
        print(f"  {prefix} [{severity}] {check}: {msg}")
        if severity == "ERROR":
            errors += 1
        elif severity == "WARN":
            warnings += 1
    if errors == 0 and warnings == 0:
        print("\u2705 All checks passed")
    else:
        print(f"\n{errors} errors, {warnings} warnings")
    return 1 if errors > 0 else 0


def cmd_status(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        print("Knowledge DB: NOT INITIALIZED")
        return 1
    conn = _get_conn(db_path)
    try:
        version = conn.execute(
            "SELECT graph_version, source_commit, compiler_version, swapped_at FROM kg_active_version WHERE singleton=1"
        ).fetchone()
        doc_count = conn.execute("SELECT COUNT(*) as c FROM kg_nodes").fetchone()["c"]
        edge_count = conn.execute("SELECT COUNT(*) as c FROM kg_edges").fetchone()["c"]
        error_count = conn.execute("SELECT COUNT(*) as c FROM op_compile_errors WHERE severity='ERROR'").fetchone()["c"]
    finally:
        conn.close()
    print(f"Knowledge DB: {db_path}")
    print(f"  Documents: {doc_count}")
    print(f"  Relations: {edge_count}")
    print(f"  Compile errors: {error_count}")
    if version:
        print(f"  Graph version: {version['graph_version']}")
        print(f"  Source commit: {version['source_commit'][:12]}")
        print(f"  Compiler: {version['compiler_version']}")
    else:
        print("  No active version")
    return 0


def cmd_compile_incremental(args) -> int:
    """Compilación incremental: solo docs modificados."""
    db_path = _resolve_db_path(args)
    source_dir = Path(args.source_dir).resolve() if hasattr(args, "source_dir") and args.source_dir else None
    from knowledge.engine.compiler import compile_incremental

    result = compile_incremental(source_dir=source_dir, db_path=db_path)
    if result.documents_changed == 0 and result.success:
        print("No changes detected (incremental skip)")
        return 0
    print(f"Compile incremental: {result.documents_changed} changed, {result.documents_total} total")
    return 0 if result.success else 1


def cmd_compile(args) -> int:
    db_path = _resolve_db_path(args)
    source_dir = Path(args.source_dir).resolve() if hasattr(args, "source_dir") and args.source_dir else None
    from knowledge.engine.orchestrator import request_compile

    n = request_compile("cli", source_dir=source_dir, db_path=db_path)
    if n:
        print("Compile OK (with flock protection)")
        return 0
    print("Compile skipped (dedup or lock held)")
    return 0
