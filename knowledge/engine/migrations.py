"""Database schema migration system.

Almacén de version: PRAGMA user_version.
Un archivo SQL por migración en schemas/migrations/.
Solo forward. Downgrade = re-init.

Atomicidad:
  - Schema completo (v0): executescript (idempotente, CREATE IF NOT EXISTS)
  - Migraciones: BEGIN...COMMIT dentro del script SQL;
    si falla, init_db cierra la conexión → transaction rollback automático
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

log = logging.getLogger("ura.knowledge.migrations")

SCHEMA_VERSION = 14  # single source of truth — bump al añadir migración
ENGINE_VERSION = "0.3.0"  # versionado semántico del Knowledge Engine
MINIMUM_SUPPORTED_SCHEMA = 5  # schema mínimo con el que este engine puede operar (migraciones desde v5+)
MAXIMUM_SUPPORTED_SCHEMA = 14  # schema máximo que este engine entiende


@dataclass(frozen=True)
class Migration:
    """Una migración de esquema de base de datos.

    Attributes:
        version: Número de versión destino (ej: 7 = v6→v7).
        description: Texto legible para logs.
        sql_file: Nombre del archivo SQL en schemas/migrations/.
                  None = migración virtual (solo version bump, sin SQL).

    """

    version: int
    description: str
    sql_file: str | None = None


MIGRATIONS: dict[int, Migration] = {
    6: Migration(
        version=6,
        description="Schema inicial (v0→v6 con executescript, no incremental)",
        sql_file=None,  # migración virtual
    ),
    7: Migration(
        version=7,
        description="Añadir columna body a kg_nodes (v6→v7)",
        sql_file="v6_to_v7.sql",
    ),
    8: Migration(
        version=8,
        description="Añadir tabla op_vector_sync (v7→v8)",
        sql_file="v7_to_v8.sql",
    ),
    9: Migration(
        version=9,
        description="Añadir determinism_hash a kg_active_version + op_archives + op_feedback_agg",
        sql_file="v8_to_v9.sql",
    ),
    10: Migration(
        version=10,
        description="Añadir determinism_algorithm a kg_active_version (sha256-v1)",
        sql_file="v9_to_v10.sql",
    ),
    11: Migration(
        version=11,
        description="Añadir tabla op_audit para auditoría best-effort",
        sql_file="v10_to_v11.sql",
    ),
    12: Migration(
        version=12,
        description="Índices para queries frecuentes (op_jobs, op_compile_errors, op_vector_sync, op_archives)",
        sql_file="v11_to_v12.sql",
    ),
    13: Migration(
        version=13,
        description="Extraer content_sha256/wraps a columnas propias + tabla op_memory",
        sql_file="v12_to_v13.sql",
    ),
    14: Migration(
        version=14,
        description="FTS5 op_assets + op_memory + op_lineage_edges + op_jobs.result_data",
        sql_file="v13_to_v14.sql",
    ),
}


# ── Version management ────────────────────────────────────────────────────────


def get_schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")


# ── Migration orchestration ────────────────────────────────────────────────────


def migrate_db(
    conn: sqlite3.Connection,
    schema_path: Path,
    migrations_dir: Path | None = None,
    target_version: int = SCHEMA_VERSION,
) -> None:
    """Migrate or initialize database to target_version.

    - PRAGMA user_version = 0 → fresh DB, apply full schema
    - PRAGMA user_version < target → apply incremental migrations
    - PRAGMA user_version == target → no-op
    - PRAGMA user_version > target → error (no downgrade)
    """
    current = get_schema_version(conn)
    if current == target_version:
        return

    if current == 0:
        schema = schema_path.read_text()
        conn.executescript(schema)
        _set_schema_version(conn, target_version)
        conn.commit()
        log.info("Fresh DB initialized to schema v%s", target_version)
        return

    if current < MINIMUM_SUPPORTED_SCHEMA:
        msg = (
            f"DB schema version {current} is too old. "
            f"Minimum supported: {MINIMUM_SUPPORTED_SCHEMA}. "
            "Run 'ke init' to rebuild."
        )
        raise ValueError(
            msg,
        )

    if current > MAXIMUM_SUPPORTED_SCHEMA:
        msg = (
            f"DB schema version {current} > maximum supported {MAXIMUM_SUPPORTED_SCHEMA}. "
            "This engine version is too old for this database. "
            "Upgrade the Knowledge Engine or run 'ke init' to rebuild."
        )
        raise ValueError(
            msg,
        )

    if current > target_version:
        msg = (
            f"DB schema version {current} > target {target_version}. Downgrade not supported. Run 'ke init' to rebuild."
        )
        raise ValueError(
            msg,
        )

    if migrations_dir is None:
        migrations_dir = schema_path.parent / "migrations"

    for version in range(current + 1, target_version + 1):
        if version not in MIGRATIONS:
            msg = (
                f"No migration defined for v{version}. "
                f"Current DB: v{current}, target: v{target_version}. "
                "Run 'ke init' to rebuild."
            )
            raise ValueError(
                msg,
            )
        mig = MIGRATIONS[version]
        if mig.sql_file:
            migration_path = migrations_dir / mig.sql_file
            if not migration_path.exists():
                msg = f"Migration file not found: {migration_path} (required for {mig.description})"
                raise FileNotFoundError(msg)
            log.info("Applying migration v%s: %s", version, mig.description)
            sql = migration_path.read_text()
            conn.executescript(f"BEGIN;\n{sql}\nCOMMIT;")
        else:
            log.info("Skipping migration v%s: %s (no SQL, version bump)", version, mig.description)
        _set_schema_version(conn, version)
        conn.commit()
        log.info("Migration v%s applied successfully", version)


# ── Verification ───────────────────────────────────────────────────────────────


def verify_migration(conn: sqlite3.Connection, expected: int = SCHEMA_VERSION) -> None:
    """Verify DB schema version matches expected. Raise on mismatch."""
    actual = get_schema_version(conn)
    if actual != expected:
        msg = f"Schema version mismatch: DB={actual}, expected={expected}. Run 'ke init' to fix."
        raise RuntimeError(msg)
