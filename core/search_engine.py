"""search_engine.py — Búsqueda full-text sobre analytics.db vía SQLite FTS5.

Proporciona índice de texto completo sobre las métricas almacenadas
y una función search() para consultarlas desde CLI o API.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("search_engine")

DB_PATH = Path(__file__).parent.parent / "data" / "processed" / "analytics.db"
FTS_TABLE = "analytics_fts"


def _ensure_fts() -> bool:
    """Crea el índice FTS5 si no existe. Retorna True si se creó."""
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(str(DB_PATH))
        # Crear tabla FTS5 virtual
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
            USING fts5(source, metric_name, content='analytics', content_rowid='id')
        """)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.warning("search_engine: error creando FTS: %s", e)
        return False


def rebuild_index() -> int:
    """Reconstruye el índice FTS desde analytics. Retorna número de filas indexadas."""
    if not _ensure_fts():
        return 0
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(f"INSERT INTO {FTS_TABLE}({FTS_TABLE}) VALUES('rebuild')")
        count = conn.execute("SELECT COUNT(*) FROM analytics").fetchone()[0]
        conn.commit()
        conn.close()
        log.info("search_engine: índice FTS reconstruido (%d filas)", count)
        return count
    except Exception as e:
        log.warning("search_engine: error rebuild: %s", e)
        return 0


def search(query: str, limit: int = 20) -> list[dict]:
    """Busca en analytics FTS5. Retorna lista de resultados."""
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT a.id, a.ts, a.source, a.metric_name, a.metric_value, a.moving_avg, a.records_count "
            f"FROM {FTS_TABLE} f JOIN analytics a ON a.id = f.rowid "
            f"WHERE {FTS_TABLE} MATCH ? "
            f"ORDER BY rank LIMIT ?",
            (query, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning("search_engine: error search '%s': %s", query, e)
        return []


def get_suggestions(prefix: str, limit: int = 5) -> list[str]:
    """Autocompletado de términos de búsqueda."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            f"SELECT DISTINCT metric_name FROM analytics WHERE metric_name LIKE ? LIMIT ?",
            (f"{prefix}%", limit),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception as e:
        log.warning("search_engine: error suggestions: %s", e)
        return []


def index_new_data() -> int:
    """Indexa filas nuevas desde la última indexación."""
    return rebuild_index()


if __name__ == "__main__":
    import sys
    if "--rebuild" in sys.argv:
        c = rebuild_index()
        print(f"Indexadas {c} filas")
    elif "--search" in sys.argv:
        q = sys.argv[sys.argv.index("--search") + 1]
        results = search(q)
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif "--suggest" in sys.argv:
        p = sys.argv[sys.argv.index("--suggest") + 1]
        print(get_suggestions(p))
    else:
        print("Uso: python3 core/search_engine.py --rebuild | --search <q> | --suggest <prefix>")
