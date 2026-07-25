from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("tuneladora.pending_queue")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_fixes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts TEXT NOT NULL,
    resolved_ts TEXT,
    bloque TEXT,
    archivo TEXT,
    linea INTEGER,
    herramienta TEXT,
    severidad TEXT,
    error_raw TEXT,
    sugerencia_llm TEXT,
    estado TEXT DEFAULT 'pendiente',
    modelo_generador TEXT,
    intentos INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tuneladora_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    model TEXT,
    mode TEXT,
    verdict TEXT NOT NULL,
    seconds REAL,
    n_files INTEGER,
    n_lines INTEGER,
    head TEXT,
    failures TEXT
);
"""


class PendingQueue:
    def __init__(self, db_path: Path) -> None:
        self._db = db_path
        self.ok = True
        try:
            self._ensure_tables()
        except (sqlite3.Error, OSError) as exc:
            log.warning("PendingQueue init failed (degraded mode): %s", exc)
            self.ok = False

    def _ensure_tables(self) -> None:
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)

    def _ok_or(self) -> bool:
        return self.ok

    def add(
        self,
        archivo: str,
        herramienta: str,
        severidad: str,
        error_raw: str,
        bloque: str = "",
        linea: int = 0,
        sugerencia_llm: str = "",
        modelo_generador: str = "",
        estado: str = "pendiente",
    ) -> int:
        if not self._ok_or():
            return 0
        with sqlite3.connect(str(self._db)) as conn:
            cur = conn.execute(
                "INSERT INTO pending_fixes (created_ts, bloque, archivo, linea, herramienta, severidad, error_raw, sugerencia_llm, modelo_generador, estado) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.strftime("%Y-%m-%dT%H:%M:%S"), bloque, archivo, linea, herramienta, severidad, error_raw, sugerencia_llm, modelo_generador, estado),
            )
            return cur.lastrowid or 0

    def list_pending(self, severidad: str | None = None) -> list[dict[str, Any]]:
        if not self._ok_or():
            return []
        with sqlite3.connect(str(self._db)) as conn:
            conn.row_factory = sqlite3.Row
            if severidad:
                rows = conn.execute(
                    "SELECT * FROM pending_fixes WHERE estado='pendiente' AND severidad=? ORDER BY severidad DESC, created_ts ASC",
                    (severidad,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM pending_fixes WHERE estado='pendiente' ORDER BY severidad DESC, created_ts ASC"
                ).fetchall()
            return [dict(r) for r in rows]

    def resolve(self, fix_id: int, estado: str = "hecho") -> None:
        if not self._ok_or():
            return
        with sqlite3.connect(str(self._db)) as conn:
            conn.execute(
                "UPDATE pending_fixes SET estado=?, resolved_ts=? WHERE id=?",
                (estado, time.strftime("%Y-%m-%dT%H:%M:%S"), fix_id),
            )

    def record_run(
        self,
        mode: str,
        verdict: str,
        seconds: float,
        n_files: int = 0,
        n_lines: int = 0,
        head: str = "",
        failures: str = "",
        model: str = "",
    ) -> int:
        if not self._ok_or():
            return 0
        with sqlite3.connect(str(self._db)) as conn:
            cur = conn.execute(
                "INSERT INTO tuneladora_runs (ts, model, mode, verdict, seconds, n_files, n_lines, head, failures) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.strftime("%Y-%m-%dT%H:%M:%S"), model, mode, verdict, seconds, n_files, n_lines, head, failures),
            )
            return cur.lastrowid or 0

    def stats(self) -> dict[str, Any]:
        if not self._ok_or():
            return {"pending_fixes": 0, "total_runs": 0, "ok_runs": 0, "fail_runs": 0}
        with sqlite3.connect(str(self._db)) as conn:
            total_pending = conn.execute("SELECT COUNT(*) FROM pending_fixes WHERE estado='pendiente'").fetchone()[0]
            total_runs = conn.execute("SELECT COUNT(*) FROM tuneladora_runs").fetchone()[0]
            ok_runs = conn.execute("SELECT COUNT(*) FROM tuneladora_runs WHERE verdict='OK'").fetchone()[0]
            fail_runs = conn.execute("SELECT COUNT(*) FROM tuneladora_runs WHERE verdict='FAIL'").fetchone()[0]
            return {
                "pending_fixes": total_pending,
                "total_runs": total_runs,
                "ok_runs": ok_runs,
                "fail_runs": fail_runs,
            }
