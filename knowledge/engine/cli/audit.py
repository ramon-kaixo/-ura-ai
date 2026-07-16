"""CLI: vacuum, audit-db."""

from knowledge.engine.cli.main import _resolve_db_path
from knowledge.engine.connection import open_db


def cmd_vacuum(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        print("DB not found", file=sys.stderr)
        return 1
    before = db_path.stat().st_size
    print(f"VACUUM: {before / 1024:.0f} KB antes...", end=" ", flush=True)
    conn = open_db(db_path)
    conn.execute("VACUUM")
    conn.close()
    after = db_path.stat().st_size
    saved = before - after
    print(f"{after / 1024:.0f} KB después (ahorrado {saved / 1024:.0f} KB)")
    return 0


def cmd_audit_db(args) -> int:
    db_path = _resolve_db_path(args)
    errors = 0

    def report(status: str, check: str, msg: str) -> None:
        nonlocal errors
        prefix = {"OK": "\u2705", "WARN": "\u26a0\ufe0f", "FAIL": "\u274c"}.get(status, "?")
        if status == "FAIL":
            errors += 1
        print(f"  {prefix} [{check}] {msg}")

    if not db_path.exists():
        report("FAIL", "db_exists", "DB file not found")
        print(f"\nErrors: {errors}")
        return 1

    report("OK", "db_exists", f"DB: {db_path}")
    print()

    conn = open_db(db_path)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity == "ok":
        report("OK", "integrity", "SQLite integrity check passed")
    else:
        report("FAIL", "integrity", f"Corruption detected: {integrity}")
    print()

    orphan_src = conn.execute(
        "SELECT COUNT(*) as c FROM kg_edges e LEFT JOIN kg_nodes n ON e.src = n.id WHERE n.id IS NULL"
    ).fetchone()["c"]
    if orphan_src:
        report("FAIL", "orphan_edges", f"{orphan_src} edges with missing source node")
    else:
        report("OK", "orphan_edges", "No orphan edge sources")
    orphan_dst = conn.execute(
        "SELECT COUNT(*) as c FROM kg_edges e LEFT JOIN kg_nodes n ON e.dst = n.id WHERE n.id IS NULL"
    ).fetchone()["c"]
    if orphan_dst:
        report("FAIL", "orphan_edges", f"{orphan_dst} edges with missing target node")
    else:
        report("OK", "orphan_dst", "No orphan edge targets")
    print()

    versions = conn.execute("SELECT COUNT(*) as c FROM kg_active_version").fetchone()["c"]
    if versions == 1:
        report("OK", "active_version", "Single active version row")
    elif versions == 0:
        report("WARN", "active_version", "No active version row (fresh DB)")
    else:
        report("FAIL", "active_version", f"{versions} active version rows (expected 1)")
    print()

    stuck = conn.execute(
        "SELECT COUNT(*) as c FROM op_jobs WHERE status = 'running' AND started_at < datetime('now', '-30 minutes')"
    ).fetchone()["c"]
    if stuck:
        report("FAIL", "stuck_jobs", f"{stuck} jobs stuck in 'running' for >30min")
    else:
        report("OK", "stuck_jobs", "No stuck jobs")
    print()

    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    if journal == "wal":
        report("OK", "wal_mode", f"Journal mode: {journal}")
    else:
        report("FAIL", "wal_mode", f"Expected WAL, got {journal}")
    wal_path = db_path.with_name(db_path.name + "-wal")
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0
    if wal_size > 100 * 1024 * 1024:
        report("WARN", "wal_size", f"WAL file: {wal_size / 1024 / 1024:.0f} MB (>100MB)")
    elif wal_size > 0:
        report("OK", "wal_size", f"WAL file: {wal_size / 1024:.0f} KB")
    else:
        report("OK", "wal_size", "No WAL file (fully checkpointed)")
    print()

    pending = conn.execute("SELECT COUNT(*) as c FROM op_vector_sync WHERE status IN ('pending', 'failed')").fetchone()[
        "c"
    ]
    if pending:
        report("WARN", "pending_sync", f"{pending} pending sync operations")
    else:
        report("OK", "pending_sync", "All sync operations done")
    print()

    try:
        from knowledge.engine.audit import get_audit

        audit = get_audit()
        if audit.backend:
            health = audit.backend.health_check()
            if health.healthy:
                report("OK", "audit", f"Audit backend healthy ({health.events_written} events)")
            else:
                report("FAIL", "audit", f"Audit backend unhealthy: {health.error}")
        else:
            report("WARN", "audit", "No audit backend configured")
    except Exception:
        report("WARN", "audit", "Could not check audit health")
    print()

    import shutil

    usage = shutil.disk_usage(db_path.parent)
    free_gb = usage.free / (1024**3)
    if free_gb < 1:
        report("FAIL", "disk_space", f"Only {free_gb:.1f} GB free on device")
    elif free_gb < 5:
        report("WARN", "disk_space", f"{free_gb:.1f} GB free on device")
    else:
        report("OK", "disk_space", f"{free_gb:.1f} GB free on device")

    conn.close()
    print(f"\n{'=' * 40}")
    print(f"Errors: {errors}")
    return 1 if errors else 0
