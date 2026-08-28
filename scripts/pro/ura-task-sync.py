#!/usr/bin/env python3
"""Propagación de tareas entre nodos del orquestador (Opción C, auditoría 2026-08-28).

Automatiza lo que antes se hacía a mano (replicar una tarea creada en la API de
un nodo a la DB local de otro nodo para que su worker la ejecute). Reversible:
no toca el núcleo; solo INSERT idempotente en la DB local destino.

Uso:
  ura-task-sync.py --task TASK-XXXX --from-api http://100.72.103.12:4097 --db data/task_queue.db
  ura-task-sync.py --task TASK-XXXX --db data/task_queue.db              # desde una DB origen
  ura-task-sync.py --task TASK-XXXX --from-db <origen> --db <destino>

Idempotente: si el task_id ya existe en la DB destino, no duplica (dedup por id).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_EVENT_INSERT = (
    "INSERT OR IGNORE INTO task_events (task_id, event, agent, details, timestamp, automatic)"
    " VALUES (?, ?, '', ?, ?, 1)"
)


def _fetch_from_api(api_url: str, task_id: str) -> dict[str, Any]:
    req = urllib.request.Request(f"{api_url}/tasks/{task_id}")  # noqa: S310
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read())


def _fetch_from_db(db_path: Path, task_id: str) -> dict[str, Any] | None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _sync(db_path: Path, task: dict[str, Any]) -> bool:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    exists = conn.execute("SELECT id FROM tasks WHERE id=?", (task["id"],)).fetchone()
    if exists:
        conn.close()
        return False
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """INSERT INTO tasks
           (id, description, plan_phase, assigned_to, status, priority, retries,
            max_retries, timeout_seconds, context_json, worktree_path, created_at,
            updated_at, completed_at, last_heartbeat, error_log, commit_sha,
            reviewer, node_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            task["id"],
            task.get("description", ""),
            task.get("plan_phase", ""),
            "",
            "pending",
            task.get("priority", 0),
            0,
            task.get("max_retries", 3),
            task.get("timeout_seconds", 1800),
            task.get("context_json", "{}"),
            "",
            task.get("created_at", now),
            now,
            "",
            "",
            "",
            "",
            "",
            task.get("node_id", ""),
        ),
    )
    conn.execute(
        _EVENT_INSERT,
        (task["id"], "synced", f"propagada desde nodo origen ({task.get('node_id', '')})", now),
    )
    conn.commit()
    conn.close()
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Propagación de tareas entre nodos (Opción C)")
    ap.add_argument("--task", required=True, help="task_id a propagar")
    ap.add_argument("--from-api", help="API origen (ej. http://100.72.103.12:4097)")
    ap.add_argument("--from-db", help="DB SQLite origen")
    ap.add_argument("--db", required=True, help="DB SQLite destino (la de este nodo)")
    args = ap.parse_args()

    if not args.from_api and not args.from_db:
        print("ERROR: necesitas --from-api o --from-db", file=sys.stderr)
        return 2

    task: dict[str, Any] | None = None
    if args.from_api:
        try:
            task = _fetch_from_api(args.from_api, args.task)
        except Exception as e:
            print(f"ERROR: no se pudo leer de API: {e}", file=sys.stderr)
            return 1
    else:
        task = _fetch_from_db(Path(args.from_db or ""), args.task)

    if not task:
        print(f"ERROR: tarea {args.task} no encontrada en el origen", file=sys.stderr)
        return 1

    from motor.orchestration.task_queue import init_db

    init_db(Path(args.db))
    inserted = _sync(Path(args.db), task)
    print(f"{'OK: insertada' if inserted else 'SKIP: ya existia'} tarea {args.task} en {args.db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
