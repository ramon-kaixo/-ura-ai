"""Fase 5: SemanticMemory — relaciones y conceptos extraídos de pipelines."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("tuneladora.memory.semantic")


@dataclass(frozen=True)
class Concept:
    name: str
    context: str
    weight: float = 1.0
    tags: tuple[str, ...] = ()
    created: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    occurrences: int = 1


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    relation_type: str
    weight: float = 1.0
    created: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticMemory:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    name TEXT PRIMARY KEY,
                    context TEXT NOT NULL DEFAULT '',
                    weight REAL NOT NULL DEFAULT 1.0,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    occurrences INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    created TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (source, target, relation_type)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rel_source ON relations(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rel_target ON relations(target)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rel_type ON relations(relation_type)
            """)
            conn.commit()

    def learn_concept(self, concept: Concept) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            existing = conn.execute(
                "SELECT weight, occurrences FROM concepts WHERE name = ? AND context = ?",
                (concept.name, concept.context),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE concepts SET weight = ?, last_seen = ?, occurrences = ? WHERE name = ? AND context = ?",
                    (concept.weight + existing[0], now, existing[1] + 1, concept.name, concept.context),
                )
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO concepts (name, context, weight, tags, created, last_seen, occurrences) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        concept.name,
                        concept.context,
                        concept.weight,
                        json.dumps(list(concept.tags)),
                        concept.created,
                        now,
                        concept.occurrences,
                    ),
                )
            conn.commit()
        log.debug("Concepto aprendido: %s (%.1f)", concept.name, concept.weight)

    def learn_relation(self, relation: Relation) -> None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO relations (source, target, relation_type, weight, created, metadata)
                VALUES (?, ?, ?, ?, COALESCE((SELECT created FROM relations WHERE source=? AND target=? AND relation_type=?), ?), ?)
                """,
                (
                    relation.source,
                    relation.target,
                    relation_type := relation.relation_type,
                    relation.weight,
                    relation.source,
                    relation.target,
                    relation_type,
                    relation.created,
                    json.dumps(relation.metadata),
                ),
            )
            conn.commit()
        log.debug("Relación aprendida: %s --[%s]--> %s", relation.source, relation.relation_type, relation.target)

    def get_concept(self, name: str) -> list[Concept]:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT name, context, weight, tags, created, last_seen, occurrences "
                "FROM concepts WHERE name = ? ORDER BY weight DESC",
                (name,),
            ).fetchall()
        return [
            Concept(
                name=r[0],
                context=r[1],
                weight=r[2],
                tags=tuple(json.loads(r[3])),
                created=r[4],
                last_seen=r[5],
                occurrences=r[6],
            )
            for r in rows
        ]

    def get_related(self, name: str, relation_type: str | None = None) -> list[Relation]:
        params: list[Any] = [name, name]
        if relation_type:
            where = "(source = ? OR target = ?) AND relation_type = ?"
            params.append(relation_type)
        else:
            where = "source = ? OR target = ?"
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute(
                f"SELECT source, target, relation_type, weight, created, metadata FROM relations WHERE {where} ORDER BY weight DESC",  # noqa: S608
                params,
            ).fetchall()
        return [
            Relation(source=r[0], target=r[1], relation_type=r[2], weight=r[3], created=r[4], metadata=json.loads(r[5]))
            for r in rows
        ]

    def search_concepts(self, query: str, limit: int = 20) -> list[Concept]:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT name, context, weight, tags, created, last_seen, occurrences "
                "FROM concepts WHERE name LIKE ? OR context LIKE ? "
                "ORDER BY weight DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [
            Concept(
                name=r[0],
                context=r[1],
                weight=r[2],
                tags=tuple(json.loads(r[3])),
                created=r[4],
                last_seen=r[5],
                occurrences=r[6],
            )
            for r in rows
        ]
