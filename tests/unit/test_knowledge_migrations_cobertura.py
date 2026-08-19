"""Tests de cobertura para knowledge/engine/migrations.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.migrations import (
    MAXIMUM_SUPPORTED_SCHEMA,
    MIGRATIONS,
    MINIMUM_SUPPORTED_SCHEMA,
    SCHEMA_VERSION,
    Migration,
    _aplicar_migracion,
    _migrar_fresh,
    _set_schema_version,
    _validar_rango,
    get_schema_version,
    migrate_db,
    verify_migration,
)

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"
SCHEMA_PATH = SCHEMA_DIR / "knowledge_graph.sql"


def _setup_v6(conn: sqlite3.Connection) -> None:
    """Schema minimo equivalente a v6 (solo tablas base; el resto lo crean las migraciones)."""
    conn.executescript(
        "CREATE TABLE kg_nodes (id TEXT PRIMARY KEY, type TEXT NOT NULL, path TEXT NOT NULL,"
        " content_sha256 TEXT NOT NULL, frontmatter TEXT NOT NULL, semantic TEXT, quality REAL,"
        " confidence REAL, embed_hash TEXT, swapped_at TEXT);"
        " CREATE TABLE kg_edges (src TEXT NOT NULL, dst TEXT NOT NULL, relation TEXT NOT NULL,"
        " metadata TEXT, PRIMARY KEY (src, dst, relation));"
        " CREATE TABLE kg_active_version (singleton INTEGER PRIMARY KEY CHECK (singleton = 1),"
        " version_id TEXT);"
        " CREATE TABLE op_jobs (id TEXT PRIMARY KEY, status TEXT, job_type TEXT);"
        " CREATE TABLE op_compile_errors (run_id TEXT, message TEXT);"
    )



@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


def test_constantes_coherentes() -> None:
    assert SCHEMA_VERSION == MAXIMUM_SUPPORTED_SCHEMA == 15
    assert MINIMUM_SUPPORTED_SCHEMA == 5
    assert len(MIGRATIONS) == SCHEMA_VERSION - 5


def test_migration_default_sql_file() -> None:
    m = Migration(version=99, description="d")
    assert m.sql_file is None


def test_get_set_schema_version(conn) -> None:
    assert get_schema_version(conn) == 0
    _set_schema_version(conn, 7)
    assert get_schema_version(conn) == 7


def test_migrate_db_noop(conn) -> None:
    _set_schema_version(conn, SCHEMA_VERSION)
    migrate_db(conn, SCHEMA_PATH)
    assert get_schema_version(conn) == SCHEMA_VERSION


def test_migrate_db_fresh(conn) -> None:
    migrate_db(conn, SCHEMA_PATH)
    assert get_schema_version(conn) == SCHEMA_VERSION
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "kg_nodes" in tables
    assert "op_assets" in tables


def test_migrate_db_incremental_14_a_15(conn) -> None:
    _setup_v6(conn)
    conn.executescript(
        "CREATE TABLE op_assets (id TEXT PRIMARY KEY, asset_type TEXT NOT NULL,"
        " metadata TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL DEFAULT '{}',"
        " relationships TEXT NOT NULL DEFAULT '[]', quality REAL NOT NULL DEFAULT 0.0,"
        " content_sha256 TEXT, wraps TEXT, created_at TEXT, updated_at TEXT);"
        " CREATE TABLE op_memory (memory_id TEXT PRIMARY KEY, title TEXT, content TEXT);"
        " CREATE VIRTUAL TABLE op_assets_fts USING fts5(id UNINDEXED, title, body);"
        " CREATE VIRTUAL TABLE op_memory_fts USING fts5(id UNINDEXED, title, content);"
    )
    _set_schema_version(conn, 14)
    migrate_db(conn, SCHEMA_PATH, target_version=15)
    assert get_schema_version(conn) == 15


def test_migrate_db_incremental_completo(conn) -> None:
    _setup_v6(conn)
    _set_schema_version(conn, 6)
    migrate_db(conn, SCHEMA_PATH, target_version=15)
    assert get_schema_version(conn) == 15


def test_migrate_db_sin_migracion_definida(conn) -> None:
    _set_schema_version(conn, 15)
    with pytest.raises(ValueError, match="No migration defined"):
        migrate_db(conn, SCHEMA_PATH, target_version=16)


def test_migrar_fresh_sin_schema(tmp_path, conn) -> None:
    with pytest.raises(FileNotFoundError):
        _migrar_fresh(conn, tmp_path / "no.sql", 15)


def test_migrar_fresh_escribe_version(tmp_path, conn) -> None:
    schema = tmp_path / "s.sql"
    schema.write_text("CREATE TABLE t (x INTEGER);")
    _migrar_fresh(conn, schema, 9)
    assert get_schema_version(conn) == 9
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='t'").fetchone()


@pytest.mark.parametrize(
    "current,target",
    [(4, 15), (16, 15), (17, 15)],
)
def test_validar_rango_rechaza(conn, current, target) -> None:
    with pytest.raises(ValueError):
        _validar_rango(current, target)


def test_validar_rango_acepta() -> None:
    _validar_rango(5, 15)
    _validar_rango(15, 15)


def test_validar_rango_downgrade() -> None:
    with pytest.raises(ValueError, match="Downgrade not supported"):
        _validar_rango(14, 13)


def test_aplicar_migracion_sql(tmp_path, conn) -> None:
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "v10_to_v11.sql").write_text("CREATE TABLE op_audit_test (x INTEGER);")
    _aplicar_migracion(conn, 11, mig_dir)
    assert get_schema_version(conn) == 11


def test_aplicar_migracion_virtual(conn) -> None:
    _aplicar_migracion(conn, 6, Path("/no/existe"))
    assert get_schema_version(conn) == 6


def test_aplicar_migracion_archivo_faltante(tmp_path, conn) -> None:
    with pytest.raises(FileNotFoundError, match="Migration file not found"):
        _aplicar_migracion(conn, 11, tmp_path)


def test_verify_migration_ok(conn) -> None:
    _set_schema_version(conn, SCHEMA_VERSION)
    verify_migration(conn)


def test_verify_migration_mismatch(conn) -> None:
    _set_schema_version(conn, 10)
    with pytest.raises(RuntimeError, match="Schema version mismatch"):
        verify_migration(conn)


def test_verify_migration_explicito(conn) -> None:
    _set_schema_version(conn, 11)
    verify_migration(conn, expected=11)
