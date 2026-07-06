"""CLI: doctor — health check."""

from knowledge.engine.cli.main import _get_conn, _resolve_db_path
from knowledge.engine.migrations import MIGRATIONS, SCHEMA_VERSION, get_schema_version
from knowledge.engine.qdrant_sync import _get_qdrant, get_pending_delete_ids
from knowledge.engine.reader import _READER_INSTANCES
from knowledge.engine.storage_verifier import check_fts_sync
from knowledge.engine.verifier import verify_graph


def cmd_doctor(args) -> int:
    db_path = _resolve_db_path(args)
    errors = 0

    def report(sev: str, check: str, msg: str) -> None:
        nonlocal errors
        prefix = {"OK": "\u2705", "WARN": "\u26a0\ufe0f", "FAIL": "\u274c"}.get(sev, "?")
        if sev == "FAIL":
            errors += 1
        print(f"  {prefix} [{check}] {msg}")

    if not db_path.exists():
        report("FAIL", "sqlite", "DB file not found")
        print(f"\n\u274c {errors} checks failed")
        return 1
    conn = _get_conn(db_path)
    try:
        v = get_schema_version(conn)
        report("OK" if v == SCHEMA_VERSION else "FAIL", "schema_version", f"v{v}" + (f" (expected v{SCHEMA_VERSION})" if v != SCHEMA_VERSION else ""))
        ver = verify_graph(db_path)
        graph_ok = all(sev != "ERROR" for sev, _, _ in ver)
        report("OK" if graph_ok else "FAIL", "graph", "Integridad correcta" if graph_ok else "Errores en grafo")
        fts = check_fts_sync(conn)
        report("OK" if not fts else "FAIL", "fts", "FTS5 sincronizado" if not fts else "; ".join(fts))
        report("OK", "reader_cache", f"{len(list(_READER_INSTANCES))} instancias activas")
        applied = sorted(m for m in MIGRATIONS if m <= v)
        pending = sorted(m for m in MIGRATIONS if m > v)
        report("WARN" if pending else "OK", "migrations", f"{len(applied)}/{len(MIGRATIONS)} aplicadas" if not pending else f"Pendientes: {pending}")
        ps = conn.execute("SELECT COUNT(*) as c FROM op_vector_sync WHERE status IN ('pending','failed')").fetchone()["c"]
        report("WARN" if ps else "OK", "pending_sync", f"{ps} pendientes" if ps else "Sin operaciones pendientes")
        dl = conn.execute("SELECT COUNT(*) as c FROM op_vector_sync WHERE status='dead_letter'").fetchone()["c"]
        report("FAIL" if dl else "OK", "dead_letter", f"{dl} abandonadas" if dl else "Sin dead letters")
        orph = get_pending_delete_ids(db_path)
        report("WARN" if orph else "OK", "orphan_vectors", f"{len(orph)} pendientes de eliminar" if orph else "Sin vectores hu\u00e9rfanos")
        qc = _get_qdrant()
        report("WARN" if qc is None else "OK", "qdrant", "No disponible" if qc is None else "Alcanzable")
        import shutil
        pc = conn.execute("PRAGMA page_count").fetchone()[0]
        fc = conn.execute("PRAGMA freelist_count").fetchone()[0]
        report("WARN" if pc > 0 and fc > pc * 0.2 else "OK", "vacuum", f"DB sin fragmentar ({fc}/{pc})" if fc <= pc * 0.2 else f"Fragmentada: {fc}/{pc}")
    finally:
        conn.close()
    print(f"\n{'✅' if errors == 0 else '❌'} All health checks passed" if errors == 0 else f"\n❌ {errors} checks failed")
    return 1 if errors else 0
