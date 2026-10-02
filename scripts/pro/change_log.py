"""Unified Change Log — registro estructurado de cambios del repositorio.

Cada commit relevante deja una entrada en data/changes.db (SQLite):
  - commit_hash, actor (human/ia), rationale (cuerpo del mensaje),
    tests_passed (0/1), docs_modified (0/1), adr_ref (número ADR si existe),
    files (lista de archivos), timestamp.

Uso:
    python3 scripts/pro/change_log.py --record <commit_hash>
    python3 scripts/pro/change_log.py --query [--limit N] [--since YYYY-MM-DD]
    python3 scripts/pro/change_log.py --actor ia    # fija actor por defecto
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "changes.db"
_ACTOR_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "change_actor.txt"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commit_hash TEXT NOT NULL UNIQUE,
            ts TEXT NOT NULL,
            actor TEXT NOT NULL,
            rationale TEXT,
            tests_passed INTEGER DEFAULT 0,
            docs_modified INTEGER DEFAULT 0,
            adr_ref TEXT,
            files TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_changes_ts ON changes (ts)")
    return conn


def _commit_info(commit_hash: str) -> dict:
    """Extrae hash, sujeto, cuerpo y archivos del commit dado."""
    out = subprocess.run(
        ["git", "show", "--format=%H%n%s%n%b", "--name-only", commit_hash],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = out.stdout or ""
    lines = stdout.splitlines()
    subject = lines[1] if len(lines) > 1 else ""
    body: list[str] = []
    files: list[str] = []
    in_body = False
    for line in lines[2:]:
        if line == "":
            if body:
                break
            in_body = True
            continue
        if in_body:
            if line.startswith(" ") and not line.startswith("  "):
                files.append(line.strip())
            else:
                body.append(line)
    return {
        "subject": subject,
        "body": " ".join(body).strip(),
        "files": files,
    }


def _detect_adr(files: list[str], subject: str) -> str | None:
    """Busca referencia ADR en el mensaje o en los archivos tocados."""
    import re

    m = re.search(r"ADR[-_]?(\d+)", subject, re.IGNORECASE)
    if m:
        return str(int(m.group(1)))
    for f in files:
        m = re.search(r"ADR[-_]?(\d+)", f, re.IGNORECASE)
        if m:
            return str(int(m.group(1)))
    return None


def record(commit_hash: str, actor: str | None = None) -> bool:
    """Registra un commit en el change log. Retorna True si se insertó."""
    info = _commit_info(commit_hash)
    if not info["subject"]:
        return False

    actor_final = actor or get_actor()
    docs = [f for f in info["files"] if f.endswith(".md") or f.startswith("docs/")]
    adr = _detect_adr(info["files"], info["subject"])

    conn = _connect()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO changes
                (commit_hash, ts, actor, rationale, tests_passed, docs_modified, adr_ref, files)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                commit_hash,
                datetime.now(UTC).isoformat(),
                actor_final,
                info["body"] or info["subject"],
                1 if "test" in info["subject"].lower() else 0,
                1 if docs else 0,
                adr,
                json.dumps(info["files"][:50]),
            ),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def get_actor() -> str:
    """Actor por defecto: 'ia' si hay archivo de marcado, 'human' si no."""
    if _ACTOR_FILE.exists():
        return _ACTOR_FILE.read_text(encoding="utf-8").strip() or "human"
    return "human"


def set_actor(actor: str) -> None:
    _ACTOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ACTOR_FILE.write_text(actor, encoding="utf-8")


def query(limit: int = 20, since: str | None = None) -> list[dict]:
    conn = _connect()
    sql = "SELECT commit_hash, ts, actor, rationale, tests_passed, docs_modified, adr_ref, files FROM changes"
    params: list[object] = []
    if since:
        sql += " WHERE ts >= ?"
        params.append(since)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [
        {
            "commit_hash": r[0],
            "ts": r[1],
            "actor": r[2],
            "rationale": r[3],
            "tests_passed": r[4],
            "docs_modified": r[5],
            "adr_ref": r[6],
            "files": r[7],
        }
        for r in rows
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd")

    rec = sub.add_parser("record", help="registrar un commit")
    rec.add_argument("commit_hash")
    rec.add_argument("--actor")

    q = sub.add_parser("query", help="consultar registros")
    q.add_argument("--limit", type=int, default=20)
    q.add_argument("--since", help="solo desde fecha YYYY-MM-DD")

    a = sub.add_parser("actor", help="fijar actor por defecto")
    a.add_argument("value", choices=["human", "ia"])

    args = parser.parse_args(argv)
    if args.cmd == "record":
        ok = record(args.commit_hash, args.actor)
        print("registrado" if ok else "ya existía o inválido")
        return 0 if ok else 1
    if args.cmd == "query":
        for entry in query(args.limit, args.since):
            print(
                f"{entry['ts'][:19]} {entry['actor']:<5} {entry['commit_hash'][:8]} "
                f"tests={entry['tests_passed']} docs={entry['docs_modified']} "
                f"adr={entry['adr_ref'] or '-'} — {entry['rationale'][:60]}"
            )
        return 0
    if args.cmd == "actor":
        set_actor(args.value)
        print(f"actor por defecto: {args.value}")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
