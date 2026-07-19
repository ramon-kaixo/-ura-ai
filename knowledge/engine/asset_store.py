"""AssetStore — almacenamiento de KnowledgeAssets en SQLite.

Implementa AssetStore(Protocol) con SQLite.
Operaciones: save, get, exists, delete, list.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
from typing import TYPE_CHECKING, Protocol

from knowledge.engine.connection import begin_immediate, open_db
from knowledge.engine.ontology.internal import (
    AssetRelationship,
    AssetSource,
    AssetType,
    KnowledgeAsset,
)

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("ura.knowledge.asset_store")


class AssetStore(Protocol):
    """Contrato para almacenes de KnowledgeAssets."""

    def save_asset(self, asset: KnowledgeAsset) -> bool: ...
    def get_asset(self, asset_id: str) -> KnowledgeAsset | None: ...
    def asset_exists(self, asset_id: str) -> bool: ...
    def delete_asset(self, asset_id: str) -> bool: ...
    def list_assets(
        self,
        asset_type: AssetType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeAsset]: ...
    def count(self, asset_type: AssetType | None = None) -> int: ...
    def search_assets(
        self,
        query: str,
        limit: int = 10,
        asset_type: AssetType | None = None,
    ) -> list[KnowledgeAsset]: ...


class SQLiteAssetStore:
    """Implementación SQLite de AssetStore.

    Almacena KnowledgeAssets en la tabla op_assets.
    Cifra en reposo: no (los metadatos no son secreto).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def save_asset(self, asset: KnowledgeAsset) -> bool:
        """Guarda o actualiza un KnowledgeAsset."""
        conn = None
        try:
            conn = open_db(self._db_path)
            begin_immediate(conn)

            rels_json = json.dumps(
                [
                    {"target_id": r.target_id, "relation": r.relation, "metadata": r.metadata}
                    for r in asset.relationships
                ],
            )
            source_json = json.dumps(
                {
                    "kind": asset.source.kind,
                    "location": asset.source.location,
                    "fetched_at": asset.source.fetched_at,
                },
            )

            conn.execute(
                "INSERT OR REPLACE INTO op_assets "
                "(id, asset_type, metadata, source, quality, created_at, updated_at, relationships) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    asset.asset_id,
                    asset.asset_type.value,
                    json.dumps(asset.metadata),
                    source_json,
                    asset.quality,
                    asset.created_at,
                    asset.updated_at,
                    rels_json,
                ),
            )
            conn.commit()
            return True
        except Exception as exc:
            log.warning("Error saving asset %s: %s", asset.asset_id, exc)
            return False
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def get_asset(self, asset_id: str) -> KnowledgeAsset | None:
        """Obtiene un KnowledgeAsset por ID."""
        conn = None
        try:
            conn = open_db(self._db_path)
            row = conn.execute(
                "SELECT id, asset_type, metadata, source, quality, created_at, updated_at, relationships "
                "FROM op_assets WHERE id = ?",
                (asset_id,),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_asset(row)
        except Exception as exc:
            log.warning("Error getting asset %s: %s", asset_id, exc)
            return None
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def asset_exists(self, asset_id: str) -> bool:
        """Verifica si un asset existe."""
        conn = None
        try:
            conn = open_db(self._db_path)
            row = conn.execute("SELECT 1 FROM op_assets WHERE id = ?", (asset_id,)).fetchone()
            return row is not None
        except Exception:
            return False
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def delete_asset(self, asset_id: str) -> bool:
        """Elimina un KnowledgeAsset."""
        conn = None
        try:
            conn = open_db(self._db_path)
            begin_immediate(conn)
            conn.execute("DELETE FROM op_assets WHERE id = ?", (asset_id,))
            conn.commit()
            return True
        except Exception as exc:
            log.warning("Error deleting asset %s: %s", asset_id, exc)
            return False
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def list_assets(
        self,
        asset_type: AssetType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeAsset]:
        """Lista KnowledgeAssets, opcionalmente filtrados por tipo."""
        conn = None
        try:
            conn = open_db(self._db_path)
            if asset_type:
                rows = conn.execute(
                    "SELECT id, asset_type, metadata, source, quality, created_at, updated_at, relationships "
                    "FROM op_assets WHERE asset_type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (asset_type.value, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, asset_type, metadata, source, quality, created_at, updated_at, relationships "
                    "FROM op_assets ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [self._row_to_asset(r) for r in rows]
        except Exception as exc:
            log.warning("Error listing assets: %s", exc)
            return []
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def count(self, asset_type: AssetType | None = None) -> int:
        """Cuenta KnowledgeAssets."""
        conn = None
        try:
            conn = open_db(self._db_path)
            if asset_type:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM op_assets WHERE asset_type = ?",
                    (asset_type.value,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as c FROM op_assets").fetchone()
            return row["c"] if row else 0
        except Exception:
            return 0
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def search_assets(self, query: str, limit: int = 10, asset_type: AssetType | None = None) -> list[KnowledgeAsset]:
        """Búsqueda FTS5 sobre assets. Fallback a LIKE si FTS5 no disponible.

        La query se sanitiza término a término para prevenir FTS5 syntax injection.
        Cada término se escapa y se une con espacio (AND implícito en FTS5).
        """
        if not query or not query.strip():
            return []

        try:
            safe = _sanitize_fts5(query)
            conn = open_db(self._db_path)
            try:
                sql = """
                    SELECT a.* FROM op_assets a
                    JOIN op_assets_fts fts ON a.rowid = fts.rowid
                    WHERE op_assets_fts MATCH ?
                """
                params: list = [safe]
                if asset_type:
                    sql += " AND a.asset_type = ?"
                    params.append(asset_type.value)
                sql += " ORDER BY rank LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql, params).fetchall()
                return [self._row_to_asset(r) for r in rows]
            finally:
                conn.close()

        except sqlite3.OperationalError:
            return self._search_assets_like(query, limit, asset_type)

    def _search_assets_like(
        self,
        query: str,
        limit: int = 10,
        asset_type: AssetType | None = None,
    ) -> list[KnowledgeAsset]:
        """Fallback LIKE: busca substring en metadata->title."""
        conn = open_db(self._db_path)
        pattern = f"%{query}%"
        sql = """
            SELECT id, asset_type, metadata, source, quality, created_at, updated_at, relationships
            FROM op_assets
            WHERE json_extract(metadata, '$.title') LIKE ?
        """
        params = [pattern]
        if asset_type:
            sql += " AND asset_type = ?"
            params.append(asset_type.value)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [self._row_to_asset(r) for r in rows]

    def _row_to_asset(self, row) -> KnowledgeAsset:
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        source_data = json.loads(row["source"]) if row["source"] else {}
        rels_raw = row["relationships"] or "[]"
        rels_data = json.loads(rels_raw)

        source = AssetSource(
            kind=source_data.get("kind", "unknown"),
            location=source_data.get("location", ""),
            fetched_at=source_data.get("fetched_at", ""),
        )
        rels = tuple(
            AssetRelationship(
                target_id=r["target_id"],
                relation=r.get("relation", "references"),
                metadata=r.get("metadata", {}),
            )
            for r in rels_data
        )
        return KnowledgeAsset(
            asset_id=row["id"],
            asset_type=AssetType(row["asset_type"]),
            metadata=metadata,
            source=source,
            relationships=rels,
            quality=float(row["quality"] or 0.0),
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )


def _sanitize_fts5(raw: str) -> str:
    """Convierte una query user en una query FTS5 segura.

    - Cada término se escapa con comillas dobles
    - Se separan por espacio (AND implícito en FTS5)
    - Previene FTS5 syntax injection
    """
    terms = raw.strip().split()
    if not terms:
        return ""
    escaped = ['"' + t.replace('"', '""') + '"' for t in terms]
    return " ".join(escaped)
