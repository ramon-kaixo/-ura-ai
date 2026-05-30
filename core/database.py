"""Stub: DatabaseManager — gestión de base de datos URA."""

import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "board.db"


class DatabaseManager:
    """Gestiona conexiones y operaciones en board.db."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        log.info("DatabaseManager inicializado: %s", self.db_path)

    def execute(self, query: str, params: tuple = ()) -> list:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(query, params)
            if query.strip().upper().startswith("SELECT"):
                return [dict(row) for row in cursor.fetchall()]
            conn.commit()
            return []
        finally:
            conn.close()

    def get_tasks(self, estado: str = None) -> list:
        if estado:
            return self.execute("SELECT * FROM tasks WHERE estado = ?", (estado,))
        return self.execute("SELECT * FROM tasks")


db_manager = DatabaseManager()
