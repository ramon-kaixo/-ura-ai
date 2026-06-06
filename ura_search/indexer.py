#!/usr/bin/env python3
"""indexer.py — Indexa contenido enriquecido para búsqueda semántica.

Usa sqlite-vss (vector search extension para SQLite) o ChromaDB.
Lee de .nervioso/ura_search/enriquecido/ y construye el índice.
"""
import argparse, json, logging, sqlite3, sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "data" / "indexer.log"
ENRIQUECIDO_DIR = Path.home() / ".nervioso" / "ura_search" / "enriquecido"
DB_PATH = Path(__file__).parent / "data" / "search.db"
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("indexer")


def _init_db():
    """Crea la base de datos de búsqueda si no existe.
    
    Usa FTS5 para búsqueda full-text sobre títulos y resúmenes.
    Es puro SQLite, no requiere extensiones externas.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
            titulo, resumen, categoria_asignada, fuente, url,
            content=''
        );
        CREATE TABLE IF NOT EXISTS metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            titulo TEXT,
            url TEXT,
            fuente TEXT,
            categoria TEXT,
            resumen TEXT,
            procesado INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


def index_all(force: bool = False) -> int:
    """Indexa todos los archivos enriquecidos en la base de datos."""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    indexados = 0

    for categoria_dir in sorted(ENRIQUECIDO_DIR.glob("*")):
        if not categoria_dir.is_dir():
            continue
        for enriched_file in sorted(categoria_dir.glob("*.enriched.json")):
            try:
                data = json.loads(enriched_file.read_text())
                url = data.get("url", "")
                
                # Verificar si ya está indexado
                if not force:
                    existing = conn.execute("SELECT id FROM metadata WHERE url = ?", (url,)).fetchone()
                    if existing:
                        continue

                # Insertar en metadata
                conn.execute(
                    "INSERT INTO metadata (ts, titulo, url, fuente, categoria, resumen) VALUES (?, ?, ?, ?, ?, ?)",
                    (data.get("ts", ""), data.get("titulo", ""), url,
                     data.get("fuente", ""), data.get("categoria_asignada", ""), data.get("resumen", ""))
                )
                doc_id = conn.lastrowid

                # Insertar en FTS5
                conn.execute(
                    "INSERT INTO search_index (rowid, titulo, resumen, categoria_asignada, fuente, url) VALUES (?, ?, ?, ?, ?, ?)",
                    (doc_id, data.get("titulo", ""), data.get("resumen", ""),
                     data.get("categoria_asignada", ""), data.get("fuente", ""), url)
                )
                indexados += 1

            except Exception as e:
                log.debug("Error indexando %s: %s", enriched_file.name, e)

    conn.commit()
    conn.close()
    log.info("✅ Indexados: %d documentos", indexados)
    return indexados


def search(query: str, limit: int = 10) -> list[dict]:
    """Busca documentos por similitud semántica (FTS5)."""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    # Sanitizar query para FTS5
    terms = " OR ".join(query.split())
    rows = conn.execute(
        "SELECT m.* FROM search_index s JOIN metadata m ON m.id = s.rowid "
        "WHERE search_index MATCH ? ORDER BY rank LIMIT ?",
        (terms, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stats() -> dict:
    """Estadísticas del índice."""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    total = conn.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
    by_cat = conn.execute("SELECT categoria, COUNT(*) as n FROM metadata GROUP BY categoria ORDER BY n DESC").fetchall()
    conn.close()
    return {"total": total, "por_categoria": {r[0]: r[1] for r in by_cat}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", action="store_true", help="Indexar archivos enriquecidos")
    p.add_argument("--search", help="Buscar en el índice")
    p.add_argument("--stats", action="store_true", help="Estadísticas")
    p.add_argument("--force", action="store_true", help="Reindexar aunque ya exista")
    args = p.parse_args()

    if args.index:
        c = index_all(force=args.force)
        print(f"Indexados: {c}")
    elif args.search:
        r = search(args.search)
        print(json.dumps(r, indent=2, ensure_ascii=False)[:500])
    elif args.stats:
        print(json.dumps(stats(), indent=2))
    else:
        p.print_help()

if __name__ == "__main__":
    main()
