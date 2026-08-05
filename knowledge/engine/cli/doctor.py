"""CLI: doctor — health check."""

from knowledge.engine.cli.main import _get_conn, _resolve_db_path
from knowledge.engine.migrations import MIGRATIONS, SCHEMA_VERSION, get_schema_version
from knowledge.engine.qdrant_sync import _get_qdrant, get_pending_delete_ids
from knowledge.engine.reader import _READER_INSTANCES
from knowledge.engine.storage_verifier import check_fts_sync
from knowledge.engine.verifier import verify_graph


def _check_schema(conn, db_path) -> tuple[str, str, str]:
    v = get_schema_version(conn)
    if v == SCHEMA_VERSION:
        return "OK", "schema_version", f"v{v}"
    return "FAIL", "schema_version", f"v{v} (expected v{SCHEMA_VERSION})"


def _check_graph(conn, db_path) -> tuple[str, str, str]:
    ver = verify_graph(db_path)
    graph_ok = all(sev != "ERROR" for sev, _, _ in ver)
    if graph_ok:
        return "OK", "graph", "Integridad correcta"
    return "FAIL", "graph", "Errores en grafo"


def _check_fts(conn, db_path) -> tuple[str, str, str]:
    fts = check_fts_sync(conn)
    if not fts:
        return "OK", "fts", "FTS5 sincronizado"
    return "FAIL", "fts", "; ".join(fts)


def _check_reader_cache(conn, db_path) -> tuple[str, str, str]:
    return "OK", "reader_cache", f"{len(list(_READER_INSTANCES))} instancias activas"


def _check_migrations(conn, db_path) -> tuple[str, str, str]:
    v = get_schema_version(conn)
    pending = sorted(m for m in MIGRATIONS if m > v)
    if pending:
        return "WARN", "migrations", f"Pendientes: {pending}"
    applied = sorted(m for m in MIGRATIONS if m <= v)
    return "OK", "migrations", f"{len(applied)}/{len(MIGRATIONS)} aplicadas"


def _check_pending_sync(conn, db_path) -> tuple[str, str, str]:
    ps = conn.execute("SELECT COUNT(*) as c FROM op_vector_sync WHERE status IN ('pending','failed')").fetchone()["c"]
    if ps:
        return "WARN", "pending_sync", f"{ps} pendientes"
    return "OK", "pending_sync", "Sin operaciones pendientes"


def _check_dead_letter(conn, db_path) -> tuple[str, str, str]:
    dl = conn.execute("SELECT COUNT(*) as c FROM op_vector_sync WHERE status='dead_letter'").fetchone()["c"]
    if dl:
        return "FAIL", "dead_letter", f"{dl} abandonadas"
    return "OK", "dead_letter", "Sin dead letters"


def _check_orphan_vectors(conn, db_path) -> tuple[str, str, str]:
    orph = get_pending_delete_ids(db_path)
    if orph:
        return "WARN", "orphan_vectors", f"{len(orph)} pendientes de eliminar"
    return "OK", "orphan_vectors", "Sin vectores huérfanos"


def _check_qdrant(conn, db_path) -> tuple[str, str, str]:
    qc = _get_qdrant()
    if qc is None:
        return "WARN", "qdrant", "No disponible"
    return "OK", "qdrant", "Alcanzable"


def _check_vacuum(conn, db_path) -> tuple[str, str, str]:
    pc = conn.execute("PRAGMA page_count").fetchone()[0]
    fc = conn.execute("PRAGMA freelist_count").fetchone()[0]
    if pc > 0 and fc > pc * 0.2:
        return "WARN", "vacuum", f"Fragmentada: {fc}/{pc}"
    return "OK", "vacuum", f"DB sin fragmentar ({fc}/{pc})"


_CHECK_FNS = [
    _check_schema,
    _check_graph,
    _check_fts,
    _check_reader_cache,
    _check_migrations,
    _check_pending_sync,
    _check_dead_letter,
    _check_orphan_vectors,
    _check_qdrant,
    _check_vacuum,
]


def cmd_doctor(args) -> int:
    db_path = _resolve_db_path(args)
    if not db_path.exists():
        return 1
    errors = 0
    conn = _get_conn(db_path)
    try:
        for check_fn in _CHECK_FNS:
            sev, _check, _msg = check_fn(conn, db_path)
            if sev == "FAIL":
                errors += 1
    finally:
        conn.close()
    return 1 if errors else 0
