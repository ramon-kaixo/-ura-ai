"""Verifier — fsck facade del grafo de conocimiento.

Combina StorageVerifier + KnowledgeVerifier en verify_graph().
Mensajes con formato: KE<XXX>|<mensaje>
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from knowledge.engine.knowledge_verifier import (
    check_cycles,
    check_duplicate_ids,
    check_duplicate_paths,
    check_ontology,
    check_orphans,
    check_referential_integrity,
    check_repeated_hashes,
    verify_hashes,
)
from knowledge.engine.migrations import SCHEMA_VERSION, get_schema_version
from knowledge.engine.storage_verifier import check_fts_sync, check_pragmas, check_schema

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("ura.knowledge.verifier")


def _get_conn(db_path: Path) -> sqlite3.Connection:
    from knowledge.engine.connection import open_db

    return open_db(db_path)


def _safe_check(severity: str, check_name: str, check_fn, *args) -> list[tuple[str, str, str]]:
    """Ejecuta un check y captura OperationalError para no crashear en DB corrupta."""
    try:
        return [(severity, check_name, m) for m in check_fn(*args)]
    except (sqlite3.OperationalError, OSError) as e:
        return [(severity, check_name, f"{check_name} no accesible: {e}")]


def verify_graph(
    db_path: Path,
    source_dir: Path | None = None,
) -> list[tuple[str, str, str]]:
    """Ejecuta todos los chequeos fsck.

    Retorna [(severidad, check, mensaje), ...]
    severidad: 'ERROR', 'WARN', 'INFO'
    mensaje: KE<XXX>|<texto>
    """
    results: list[tuple[str, str, str]] = []

    if not db_path.exists():
        results.append(("ERROR", "db_exists", "knowledge.db no existe"))
        return results

    conn = _get_conn(db_path)

    # Schema version check
    try:
        db_version = get_schema_version(conn)
        if db_version != SCHEMA_VERSION:
            results.append(
                ("ERROR", "schema_version", f"Schema version mismatch: DB={db_version}, expected={SCHEMA_VERSION}"),
            )
        else:
            results.append(("INFO", "schema_version", f"Schema v{db_version} OK"))
    except Exception as e:
        results.append(("ERROR", "schema_version", f"Could not read schema version: {e}"))

    # StorageVerifier
    results.extend(_safe_check("ERROR", "pragma", check_pragmas, conn))
    results.extend(_safe_check("ERROR", "schema", check_schema, conn))
    results.extend(_safe_check("ERROR", "fts_sync", check_fts_sync, conn))

    # KnowledgeVerifier
    results.extend(_safe_check("WARN", "duplicate_id", check_duplicate_ids, conn))
    results.extend(_safe_check("WARN", "duplicate_path", check_duplicate_paths, conn))
    results.extend(_safe_check("WARN", "repeated_hash", check_repeated_hashes, conn))
    results.extend(_safe_check("ERROR", "referential", check_referential_integrity, conn))
    results.extend(_safe_check("WARN", "orphans", check_orphans, conn))
    results.extend(_safe_check("WARN", "cycles", check_cycles, conn))
    results.extend(_safe_check("WARN", "ontology", check_ontology, conn))
    results.extend(_safe_check("ERROR", "hashes", verify_hashes, conn, source_dir))

    # Version info
    try:
        version = conn.execute(
            "SELECT graph_version, source_commit, compiler_version, swapped_at FROM kg_active_version WHERE singleton=1",
        ).fetchone()
    except sqlite3.OperationalError:
        version = None
    if version:
        commit = version["source_commit"][:12]
        msg = f"v{version['graph_version']}, commit={commit}"
        msg += f", compiler={version['compiler_version']}, swapped={version['swapped_at']}"
        results.append(("INFO", "version", msg))
    else:
        results.append(("INFO", "version", "Sin versión activa (DB vacía)"))

    # Last compile errors from log
    try:
        errors_from_log = conn.execute(
            "SELECT error_code, severity, message FROM op_compile_errors ORDER BY created_at DESC LIMIT 20",
        ).fetchall()
        if errors_from_log:
            for e in errors_from_log:
                results.append((e["severity"], e["error_code"], e["message"]))  # noqa: PERF401
    except sqlite3.OperationalError:
        pass

    conn.close()
    return results
