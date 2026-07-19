"""GovernanceStore — políticas de acceso y auditoría.

Implementa GovernanceStore(Protocol) con SQLite.
Permite definir políticas por asset y verificar permisos.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from knowledge.engine.connection import begin_immediate, open_db

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("ura.knowledge.governance_store")


class GovernanceStore(Protocol):
    """Contrato para almacenes de gobernanza."""

    def set_policy(self, asset_id: str, policy: dict[str, Any], actor: str = "system") -> bool: ...
    def check(self, asset_id: str, action: str, actor: str) -> bool: ...
    def get_policies(self, asset_id: str) -> list[dict[str, Any]]: ...
    def list_policies(self, limit: int = 100) -> list[dict[str, Any]]: ...


class SQLiteGovernanceStore:
    """Implementación SQLite de GovernanceStore.

    Almacena políticas en la tabla op_governance.
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path

    def set_policy(self, asset_id: str, policy: dict[str, Any], actor: str = "system") -> bool:
        """Define una política para un asset."""
        conn = None
        try:
            conn = open_db(self._db_path)
            begin_immediate(conn)
            conn.execute(
                "INSERT INTO op_governance (asset_id, policy, actor, created_at) VALUES (?, ?, ?, ?)",
                (asset_id, json.dumps(policy), actor, datetime.now(UTC).isoformat()),
            )
            conn.commit()
            return True
        except Exception as exc:
            log.warning("Error setting policy for %s: %s", asset_id, exc)
            return False
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def check(self, asset_id: str, action: str, actor: str) -> bool:
        """Verifica si un actor puede realizar una acción sobre un asset.

        Las políticas definen acciones y roles permitidos.
        Ejemplo de policy:
          {"action": "read", "roles": ["admin", "editor"]}
          {"action": "delete", "roles": ["admin"]}
        """
        conn = None
        try:
            conn = open_db(self._db_path)
            rows = conn.execute(
                "SELECT policy FROM op_governance WHERE asset_id = ? ORDER BY id DESC",
                (asset_id,),
            ).fetchall()

            for row in rows:
                try:
                    p = json.loads(row["policy"]) if isinstance(row["policy"], str) else row.get("policy", {})
                    if p.get("action") == action:
                        allowed_roles = p.get("roles", [])
                        if not allowed_roles:
                            continue
                        return actor in allowed_roles
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

            return True
        except Exception as exc:
            log.warning("Error checking policy for %s: %s", asset_id, exc)
            return True
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def get_policies(self, asset_id: str) -> list[dict[str, Any]]:
        """Retorna todas las políticas de un asset."""
        conn = None
        try:
            conn = open_db(self._db_path)
            rows = conn.execute(
                "SELECT id, asset_id, policy, actor, created_at FROM op_governance "
                "WHERE asset_id = ? ORDER BY created_at DESC",
                (asset_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            log.warning("Error getting policies: %s", exc)
            return []
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    def list_policies(self, limit: int = 100) -> list[dict[str, Any]]:
        """Lista todas las políticas."""
        conn = None
        try:
            conn = open_db(self._db_path)
            rows = conn.execute(
                "SELECT id, asset_id, policy, actor, created_at FROM op_governance ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            log.warning("Error listing policies: %s", exc)
            return []
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()
