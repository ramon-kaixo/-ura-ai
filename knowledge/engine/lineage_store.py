"""LineageStore — almacenamiento de eventos OpenLineage.

Implementa LineageStore(Protocol) con SQLite.
Permite registrar eventos de lineage y consultar upstream/downstream de un asset.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from knowledge.engine.connection import begin_immediate, open_db

log = logging.getLogger("ura.knowledge.lineage_store")


class LineageStore(Protocol):
    """Contrato para almacenes de lineage."""

    def store_lineage_event(self, event: dict[str, Any]) -> bool: ...
    def get_lineage(self, asset_id: str) -> list[dict[str, Any]]: ...
    def get_upstream(self, asset_id: str) -> list[str]: ...
    def get_downstream(self, asset_id: str) -> list[str]: ...


class SQLiteLineageStore:
    """Implementación SQLite de LineageStore.

    Almacena eventos OpenLineage en la tabla op_lineage.
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path

    def store_lineage_event(self, event: dict[str, Any]) -> bool:
        """Almacena un evento OpenLineage y sus aristas en op_lineage_edges."""
        conn = None
        try:
            conn = open_db(self._db_path)
            begin_immediate(conn)
            cur = conn.execute(
                "INSERT INTO op_lineage "
                "(event_type, event_time, run_id, job_name, namespace, "
                " input_ids, output_ids, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.get("eventType", "COMPLETE"),
                    event.get("eventTime", datetime.now(UTC).isoformat()),
                    event.get("run", {}).get("runId", ""),
                    event.get("job", {}).get("name", ""),
                    event.get("job", {}).get("namespace", ""),
                    json.dumps([i.get("name", "") for i in event.get("inputs", [])]),
                    json.dumps([o.get("name", "") for o in event.get("outputs", [])]),
                    json.dumps(event.get("facets", {})),
                ),
            )
            event_id = cur.lastrowid

            # Poblar op_lineage_edges (producto cartesiano inputs x outputs)
            inputs = [i.get("name", "") for i in event.get("inputs", [])]
            outputs = [o.get("name", "") for o in event.get("outputs", [])]
            event_time = event.get("eventTime", datetime.now(UTC).isoformat())
            event_type = event.get("eventType", "COMPLETE")
            for src in inputs:
                for dst in outputs:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO op_lineage_edges "
                            "(src, dst, relation, event_id, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (src, dst, event_type, event_id, event_time),
                        )
                    except sqlite3.OperationalError as exc:
                        # op_lineage_edges no existe (pre-migración) — ignorar
                        if "no such table" not in str(exc):
                            raise
            conn.commit()
            return True
        except Exception as exc:
            log.warning("Error storing lineage event: %s", exc)
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_lineage(self, asset_id: str) -> list[dict[str, Any]]:
        """Retorna eventos de lineage que involucran un asset."""
        conn = None
        try:
            conn = open_db(self._db_path)
            pattern = f"%{asset_id}%"
            rows = conn.execute(
                "SELECT id, event_type, event_time, run_id, job_name, namespace, "
                "       input_ids, output_ids, metadata "
                "FROM op_lineage "
                "WHERE input_ids LIKE ? OR output_ids LIKE ? "
                "ORDER BY event_time DESC LIMIT 100",
                (pattern, pattern),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            log.warning("Error getting lineage: %s", exc)
            return []
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _get_upstream_edges(self, asset_id: str) -> list[str] | None:
        """Retorna upstream desde op_lineage_edges. None si la tabla no existe."""
        conn = None
        try:
            conn = open_db(self._db_path)
            rows = conn.execute("SELECT DISTINCT src FROM op_lineage_edges WHERE dst = ?", (asset_id,)).fetchall()
            return [r["src"] for r in rows]
        except sqlite3.OperationalError:
            return None
        finally:
            if conn is not None:
                conn.close()

    def _get_downstream_edges(self, asset_id: str) -> list[str] | None:
        """Retorna downstream desde op_lineage_edges. None si la tabla no existe."""
        conn = None
        try:
            conn = open_db(self._db_path)
            rows = conn.execute("SELECT DISTINCT dst FROM op_lineage_edges WHERE src = ?", (asset_id,)).fetchall()
            return [r["dst"] for r in rows]
        except sqlite3.OperationalError:
            return None
        finally:
            if conn is not None:
                conn.close()

    def get_upstream(self, asset_id: str) -> list[str]:
        """Retorna IDs de assets que son entrada del asset consultado.

        Ruta primaria: op_lineage_edges (indexado, sin LIKE).
        Fallback: LIKE sobre JSON arrays en op_lineage.
        """
        edges = self._get_upstream_edges(asset_id)
        if edges is not None:
            return edges

        # Fallback LIKE
        events = self.get_lineage(asset_id)
        upstream: set[str] = set()
        for ev in events:
            try:
                inputs = json.loads(ev["input_ids"]) if isinstance(ev["input_ids"], str) else ev.get("input_ids", [])
                for inp in inputs:
                    if inp != asset_id:
                        upstream.add(inp)
            except (json.JSONDecodeError, KeyError):
                pass
        return sorted(upstream)

    def get_downstream(self, asset_id: str) -> list[str]:
        """Retorna IDs de assets que dependen del asset consultado.

        Ruta primaria: op_lineage_edges (indexado, sin LIKE).
        Fallback: LIKE sobre JSON arrays en op_lineage.
        """
        edges = self._get_downstream_edges(asset_id)
        if edges is not None:
            return edges

        # Fallback LIKE
        events = self.get_lineage(asset_id)
        downstream: set[str] = set()
        for ev in events:
            try:
                outputs = (
                    json.loads(ev["output_ids"]) if isinstance(ev["output_ids"], str) else ev.get("output_ids", [])
                )
                for out in outputs:
                    if out != asset_id:
                        downstream.add(out)
            except (json.JSONDecodeError, KeyError):
                pass
        return sorted(downstream)
