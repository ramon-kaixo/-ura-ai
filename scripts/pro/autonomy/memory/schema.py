"""Schema SQLite para memoria semántica + migraciones.

Tablas:
  migrations     → control de versiones del schema
  executions     → cada ejecución del ledger
  goals          → objetivos de autonomía
  plugins_times  → duración por plugin por ejecución
  decisions      → decisiones registradas
  knowledge      → conocimiento extraído
  recommendations → recomendaciones generadas
  policies       → políticas aplicadas

Schema version actual: 1
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

SCHEMA_VERSION = 1

MIGRATIONS = {
    1: """
        CREATE TABLE IF NOT EXISTS migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS executions (
            execution_id TEXT PRIMARY KEY,
            pipeline TEXT NOT NULL,
            engine_version TEXT,
            start_time TEXT,
            end_time TEXT,
            duration_ms INTEGER,
            result TEXT,
            promotion INTEGER DEFAULT 0,
            rollback INTEGER DEFAULT 0,
            host TEXT,
            git_commit_before TEXT,
            git_commit_after TEXT,
            changed_files INTEGER DEFAULT 0,
            changed_lines INTEGER DEFAULT 0,
            plugins_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS goals (
            goal_id TEXT,
            execution_id TEXT,
            title TEXT,
            priority TEXT,
            status TEXT,
            created_at TEXT,
            PRIMARY KEY (goal_id, execution_id),
            FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
        );

        CREATE TABLE IF NOT EXISTS plugin_durations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT NOT NULL,
            plugin_name TEXT NOT NULL,
            duration_s REAL,
            status TEXT,
            FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            details TEXT,
            timestamp TEXT,
            FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
        );

        CREATE TABLE IF NOT EXISTS knowledge_entries (
            id TEXT PRIMARY KEY,
            claim TEXT,
            evidence TEXT,
            confidence REAL,
            category TEXT,
            source TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id TEXT PRIMARY KEY,
            execution_id TEXT,
            title TEXT,
            evidence TEXT,
            confidence REAL,
            impact TEXT,
            risk TEXT,
            policy TEXT,
            applied INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id TEXT,
            policy_name TEXT,
            action TEXT,
            applied_at TEXT,
            status TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_plugin_durations_exec
            ON plugin_durations(execution_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_exec
            ON decisions(execution_id);
        CREATE INDEX IF NOT EXISTS idx_goals_exec
            ON goals(execution_id);
        CREATE INDEX IF NOT EXISTS idx_executions_start
            ON executions(start_time);
        CREATE INDEX IF NOT EXISTS idx_executions_pipeline
            ON executions(pipeline);
        CREATE INDEX IF NOT EXISTS idx_knowledge_category
            ON knowledge_entries(category);
    """,
}


def get_schema_version(db: sqlite3.Connection) -> int:
    try:
        row = db.execute("SELECT MAX(version) FROM migrations").fetchone()
        return row[0] or 0
    except sqlite3.OperationalError:
        return 0


def migrate(db: sqlite3.Connection, db_path: Path) -> None:
    """Aplica migraciones pendientes."""
    current = get_schema_version(db)
    for version in sorted(MIGRATIONS):
        if version > current:
            db.executescript(MIGRATIONS[version])
            db.execute(
                "INSERT INTO migrations (version, applied_at) VALUES (?, datetime('now'))",
                (version,),
            )
            db.commit()
