"""Rollback transaccional — savepoints para operaciones atómicas.

Permite deshacer operaciones parciales si algo falla durante el compile.
Usa SAVEPOINT de SQLite (anidables, no afectan a transacciones externas).

Uso:
    with transaction(conn, "compile") as state:
        state.save("pre_swap", {"graph_version": v})
        # ... operaciones ...
        if error:
            state.rollback_to("pre_swap")
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("ura.knowledge.rollback")


@dataclass
class Savepoint:
    """Un punto de restauración dentro de una transacción."""

    name: str
    data: dict[str, Any] = field(default_factory=dict)


@contextmanager
def transaction(db_path: Path, name: str = "tx"):
    """Context manager para transacciones con rollback.

    Uso:
        with transaction(db_path, "compile") as tx:
            tx.savepoint("pre_write", {"graph_version": 5})
            # ... work ...
            if failed:
                tx.rollback_to("pre_write")
    """
    from knowledge.engine.connection import begin_immediate, open_db

    conn = open_db(db_path)
    begin_immediate(conn)

    tx = TransactionManager(conn, name)
    try:
        yield tx
        conn.commit()
        log.debug("Transaction %s committed", name)
    except Exception:
        conn.rollback()
        log.warning("Transaction %s rolled back", name)
        raise
    finally:
        conn.close()


class TransactionManager:
    """Maneja savepoints dentro de una transacción SQLite."""

    def __init__(self, conn, name: str = "tx"):
        self._conn = conn
        self._name = name
        self._savepoints: list[Savepoint] = []

    def savepoint(self, name: str, data: dict[str, Any] | None = None) -> Savepoint:
        """Crea un savepoint."""
        sp = Savepoint(name=f"{self._name}_{name}", data=data or {})
        self._conn.execute(f"SAVEPOINT {sp.name}")
        self._savepoints.append(sp)
        log.debug("Savepoint %s created", sp.name)
        return sp

    def rollback_to(self, name: str) -> None:
        """Restaura a un savepoint por nombre."""
        for sp in reversed(self._savepoints):
            if sp.name.endswith(f"_{name}"):
                self._conn.execute(f"ROLLBACK TO {sp.name}")
                log.info("Rolled back to savepoint %s", sp.name)
                return
        log.warning("Savepoint %s not found for rollback", name)

    def release(self, name: str) -> None:
        """Libera un savepoint (opcional)."""
        for sp in reversed(self._savepoints):
            if sp.name.endswith(f"_{name}"):
                self._conn.execute(f"RELEASE {sp.name}")
                self._savepoints.remove(sp)
                return


# ── Snapshot rollback para compilaciones ────────────────────────────────────


class CompileRollback:
    """Rollback específico para operaciones de compile.

    Guarda el estado antes de un compile y permite restaurarlo.
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._snapshot_path = db_path.with_suffix(".db.compile_snapshot")

    def save_pre_compile_state(self) -> None:
        """Guarda el estado actual de kg_* antes del compile."""
        import shutil

        if self._db_path.exists():
            shutil.copy2(self._db_path, self._snapshot_path)
            self._copy_wal(self._db_path, self._snapshot_path)
            log.debug("Pre-compile state saved to %s", self._snapshot_path)

    def restore_pre_compile_state(self) -> bool:
        """Restaura el estado previo al compile."""
        import shutil

        if not self._snapshot_path.exists():
            return False
        try:
            shutil.copy2(self._snapshot_path, self._db_path)
            self._copy_wal(self._snapshot_path, self._db_path)
            self._snapshot_path.unlink(missing_ok=True)
            log.info("Pre-compile state restored")
            return True
        except Exception as exc:
            log.error("Failed to restore pre-compile state: %s", exc)
            return False

    def cleanup(self) -> None:
        """Elimina el snapshot de rollback."""
        self._snapshot_path.unlink(missing_ok=True)

    @staticmethod
    def _copy_wal(src: Path, dst: Path) -> None:
        import shutil

        src_wal = src.with_suffix(".db-wal")
        src_shm = src.with_suffix(".db-shm")
        if src_wal.exists():
            shutil.copy2(src_wal, dst.with_suffix(".db-wal"))
        if src_shm.exists():
            shutil.copy2(src_shm, dst.with_suffix(".db-shm"))
