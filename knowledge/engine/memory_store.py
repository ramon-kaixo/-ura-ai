"""MemoryStore — almacenamiento persistente de conversaciones, decisiones e incidencias.

Implementa MemoryStore(Protocol) con SQLite.
Soporta búsqueda full-text básica (FTS5).
Preparado para sustituir el backend por un vector store en el futuro.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from knowledge.engine.asset_store import _sanitize_fts5
from knowledge.engine.connection import begin_immediate, open_db

log = logging.getLogger("ura.knowledge.memory_store")


@dataclass(frozen=True)
class MemoryRecord:
    """Registro de memoria persistente.

    kind: conversation | decision | incident | learning | note
    related_assets: IDs de KnowledgeAssets relacionados.
    metadata: diccionario extensible para campos específicos del tipo.
    """

    memory_id: str
    kind: str  # conversation | decision | incident | learning | note
    title: str
    content: str
    related_assets: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "kind": self.kind,
            "title": self.title,
            "content": self.content[:500],
            "related_assets": list(self.related_assets),
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


class MemoryStore(Protocol):
    """Contrato para almacenes de memoria."""

    def save(self, record: MemoryRecord) -> bool: ...
    def get(self, memory_id: str) -> MemoryRecord | None: ...
    def list(self, kind: str | None = None, limit: int = 100, offset: int = 0) -> list[MemoryRecord]: ...
    def delete(self, memory_id: str) -> bool: ...
    def search(self, query: str, kind: str | None = None, limit: int = 10) -> list[MemoryRecord]: ...
    def link_asset(self, memory_id: str, asset_id: str) -> bool: ...
    def count(self, kind: str | None = None) -> int: ...


class SQLiteMemoryStore:
    """Implementación SQLite de MemoryStore.

    Tabla: op_memory (existente en schema v13).
    Búsqueda: FTS5 sobre title y content.
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path

    def save(self, record: MemoryRecord, timeout: float = 15.0) -> bool:
        """Guarda o actualiza un registro de memoria.

        Args:
            record: Registro a guardar.
            timeout: Timeout para BEGIN IMMEDIATE (default 15s para contenido grande).
        """
        conn = None
        try:
            conn = open_db(self._db_path)
            begin_immediate(conn, timeout=timeout)
            now = datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO op_memory "
                "(memory_id, kind, title, content, related_assets, tags, metadata, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.memory_id,
                    record.kind,
                    record.title,
                    record.content,
                    json.dumps(list(record.related_assets)),
                    json.dumps(list(record.tags)),
                    json.dumps(record.metadata),
                    record.created_at or now,
                    now,
                ),
            )
            conn.commit()
            return True
        except Exception as exc:
            log.warning("Error saving memory %s: %s", record.memory_id, exc)
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get(self, memory_id: str) -> MemoryRecord | None:
        try:
            conn = open_db(self._db_path)
            row = conn.execute(
                "SELECT memory_id, kind, title, content, related_assets, tags, metadata, created_at, updated_at "
                "FROM op_memory WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
            conn.close()
            if row is None:
                return None
            return self._row_to_record(row)
        except Exception as exc:
            log.warning("Error getting memory %s: %s", memory_id, exc)
            return None

    def list(self, kind: str | None = None, limit: int = 100, offset: int = 0) -> list[MemoryRecord]:
        try:
            conn = open_db(self._db_path)
            if kind:
                rows = conn.execute(
                    "SELECT memory_id, kind, title, content, related_assets, tags, metadata, created_at, updated_at "
                    "FROM op_memory WHERE kind = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (kind, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT memory_id, kind, title, content, related_assets, tags, metadata, created_at, updated_at "
                    "FROM op_memory ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            conn.close()
            return [self._row_to_record(r) for r in rows]
        except Exception as exc:
            log.warning("Error listing memories: %s", exc)
            return []

    def delete(self, memory_id: str) -> bool:
        conn = None
        try:
            conn = open_db(self._db_path)
            begin_immediate(conn)
            conn.execute("DELETE FROM op_memory WHERE memory_id = ?", (memory_id,))
            conn.commit()
            return True
        except Exception as exc:
            log.warning("Error deleting memory %s: %s", memory_id, exc)
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def search(self, query: str, kind: str | None = None, limit: int = 10) -> list[MemoryRecord]:
        """Búsqueda FTS5 sobre memorias. Fallback a LIKE si FTS5 no disponible."""
        if not query or not query.strip():
            return []

        try:
            safe = _sanitize_fts5(query)
            conn = open_db(self._db_path)
            try:
                sql = """
                    SELECT m.* FROM op_memory m
                    JOIN op_memory_fts fts ON m.rowid = fts.rowid
                    WHERE op_memory_fts MATCH ?
                """
                params: list = [safe]
                if kind:
                    sql += " AND m.kind = ?"
                    params.append(kind)
                sql += " ORDER BY rank LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql, params).fetchall()
                return [self._row_to_record(r) for r in rows]
            finally:
                conn.close()

        except sqlite3.OperationalError:
            return self._search_like(query, kind, limit)

    def _search_like(self, query: str, kind: str | None = None, limit: int = 10) -> list[MemoryRecord]:
        """Fallback LIKE original."""
        conn = open_db(self._db_path)
        pattern = f"%{query}%"
        if kind:
            rows = conn.execute(
                "SELECT memory_id, kind, title, content, related_assets, tags, metadata, "
                "       created_at, updated_at "
                "FROM op_memory WHERE kind = ? AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY created_at DESC LIMIT ?",
                (kind, pattern, pattern, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT memory_id, kind, title, content, related_assets, tags, metadata, "
                "       created_at, updated_at "
                "FROM op_memory WHERE title LIKE ? OR content LIKE ? "
                "ORDER BY created_at DESC LIMIT ?",
                (pattern, pattern, limit),
            ).fetchall()
        conn.close()
        return [self._row_to_record(r) for r in rows]

    def link_asset(self, memory_id: str, asset_id: str) -> bool:
        """Vincula un asset de conocimiento a un registro de memoria."""
        conn = None
        try:
            record = self.get(memory_id)
            if record is None:
                return False
            if asset_id in record.related_assets:
                return True
            new_assets = list(record.related_assets) + [asset_id]
            conn = open_db(self._db_path)
            begin_immediate(conn)
            conn.execute(
                "UPDATE op_memory SET related_assets = ?, updated_at = ? WHERE memory_id = ?",
                (json.dumps(new_assets), datetime.now(UTC).isoformat(), memory_id),
            )
            conn.commit()
            return True
        except Exception as exc:
            log.warning("Error linking asset %s to memory %s: %s", asset_id, memory_id, exc)
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def count(self, kind: str | None = None) -> int:
        try:
            conn = open_db(self._db_path)
            if kind:
                row = conn.execute("SELECT COUNT(*) as c FROM op_memory WHERE kind = ?", (kind,)).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as c FROM op_memory").fetchone()
            conn.close()
            return row["c"] if row else 0
        except Exception:
            return 0

    def _row_to_record(self, row) -> MemoryRecord:
        def _safe_json(val, default=None):
            if val is None:
                return default if default is not None else ([] if isinstance(default, list) else {})
            try:
                return json.loads(val) if isinstance(val, str) else val
            except (json.JSONDecodeError, TypeError):
                return default if default is not None else ([] if isinstance(default, list) else {})

        # sqlite3.Row supports dict-like access with []
        related = _safe_json(row["related_assets"] if row["related_assets"] else "[]", [])
        tags = _safe_json(row["tags"] if row["tags"] else "[]", [])
        meta = _safe_json(row["metadata"] if row["metadata"] else "{}", {})
        return MemoryRecord(
            memory_id=row["memory_id"],
            kind=row["kind"],
            title=row["title"],
            content=row["content"],
            related_assets=tuple(related),
            tags=tuple(tags),
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] if row["updated_at"] else "",
            metadata=meta if isinstance(meta, dict) else {},
        )
