"""StorageVerifier — verificaciones de la capa de almacenamiento SQLite (KE1xx).

Chequeos:
  - PRAGMAs (WAL, FOREIGN KEY, synchronous)
  - Schema SQL (tablas esperadas)
  - FTS5 sincronizado con kg_nodes
"""

from __future__ import annotations

import sqlite3


def check_pragmas(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    if fk != 1:
        issues.append(f"KE110|FOREIGN KEY desactivado (={fk})")
    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    if journal != "wal":
        issues.append(f"KE111|journal_mode no es WAL (={journal})")
    sync = conn.execute("PRAGMA synchronous").fetchone()[0]
    if sync not in (1, 2):
        issues.append(f"KE111|synchronous no recomendado (={sync}, esperado 1 o 2)")
    return issues


def check_schema(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    expected = {
        "kg_nodes",
        "kg_edges",
        "kg_nodes_fts",
        "kg_ontology_nodes",
        "kg_ontology_edges",
        "kg_active_version",
        "op_events",
        "op_audit",
        "op_jobs",
        "op_scheduler",
        "op_compiler_runs",
        "op_compile_errors",
        "op_vector_sync",
        "op_archives",
        "op_feedback_agg",
        "op_assets",
        "op_lineage",
        "op_governance",
        "op_memory",
    }
    system_tables = {
        "sqlite_sequence",
        "kg_nodes_fts_config",
        "kg_nodes_fts_content",
        "kg_nodes_fts_data",
        "kg_nodes_fts_docsize",
        "kg_nodes_fts_idx",
    }
    missing = expected - tables
    extra = tables - expected - system_tables
    if missing:
        issues.append(f"Faltan tablas: {sorted(missing)}")
    if extra:
        issues.append(f"Tablas extrañas: {sorted(extra)}")
    return issues


def check_fts_sync(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    try:
        node_count = conn.execute("SELECT COUNT(*) as c FROM kg_nodes").fetchone()["c"]
        fts_count = conn.execute("SELECT COUNT(*) as c FROM kg_nodes_fts").fetchone()["c"]
        if node_count != fts_count:
            issues.append(f"KE109|FTS5 desincronizado: {node_count} nodes vs {fts_count} en FTS")
        # Second-level check: verify every kg_nodes id has a corresponding FTS entry
        if node_count > 0:
            missing = conn.execute(
                "SELECT n.id FROM kg_nodes n WHERE NOT EXISTS (SELECT 1 FROM kg_nodes_fts f WHERE f.id = n.id) LIMIT 11"
            ).fetchall()
            if missing:
                ids_str = ", ".join(r["id"] for r in missing[:10])
                if len(missing) > 10:
                    ids_str += f" … y {node_count - 10} más"
                issues.append(f"KE109|IDs en kg_nodes sin entrada FTS: {ids_str}")
    except sqlite3.OperationalError as e:
        issues.append(f"KE109|FTS5 no accesible: {e}")
    return issues
