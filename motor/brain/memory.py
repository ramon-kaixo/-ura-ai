"""Memoria del cerebro — SQLite local, estructurado, consultable."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path.home() / ".nervioso" / "brain_memory.db"


@dataclass
class ProposalRecord:
    target_file: str = ""
    proposal_type: str = ""
    reason: str = ""
    priority: str = ""
    approved: bool | None = None
    result: str | None = None
    notes: str = ""
    id: int | None = None
    timestamp: str = ""


class BrainMemory:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    target_file TEXT NOT NULL,
                    proposal_type TEXT NOT NULL,
                    reason TEXT,
                    priority TEXT,
                    approved INTEGER,
                    result TEXT,
                    notes TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_target ON proposals(target_file)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON proposals(proposal_type)")
            conn.commit()

    def save(self, record: ProposalRecord) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "INSERT INTO proposals (timestamp, target_file, proposal_type, reason, priority, approved, result, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(),
                    record.target_file,
                    record.proposal_type,
                    record.reason,
                    record.priority,
                    1 if record.approved is True else (0 if record.approved is False else None),
                    record.result,
                    record.notes,
                ),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def get_for_target(self, target_file: str, limit: int = 10) -> list[ProposalRecord]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM proposals WHERE target_file = ? ORDER BY timestamp DESC LIMIT ?",
                (target_file, limit),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def get_failed(self, proposal_type: str | None = None, limit: int = 20) -> list[ProposalRecord]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if proposal_type:
                rows = conn.execute(
                    "SELECT * FROM proposals WHERE result = 'failed' AND proposal_type = ? ORDER BY timestamp DESC LIMIT ?",
                    (proposal_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM proposals WHERE result = 'failed' ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def get_success_patterns(self) -> dict[str, int]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT proposal_type, result, COUNT(*) as count FROM proposals WHERE approved = 1 GROUP BY proposal_type, result"
            ).fetchall()
            return {f"{r[0]}:{r[1]}": r[2] for r in rows}

    def should_propose_again(self, target_file: str, proposal_type: str) -> bool:
        history = self.get_for_target(target_file)
        for h in history:
            if h.proposal_type == proposal_type:
                if h.result == "failed":
                    return False
                if h.result == "success" and h.approved:
                    return False
        return True

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ProposalRecord:
        return ProposalRecord(
            id=row["id"],
            timestamp=row["timestamp"],
            target_file=row["target_file"],
            proposal_type=row["proposal_type"],
            reason=row["reason"],
            priority=row["priority"],
            approved=None if row["approved"] is None else bool(row["approved"]),
            result=row["result"],
            notes=row["notes"],
        )
