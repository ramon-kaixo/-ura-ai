#!/usr/bin/env python3
"""data_analyzer.py — Procesador de datos JSONL con persistencia SQLite.

Corrutina #17 del ura-supervisor. Lee data/raw/*.jsonl línea a línea,
calcula métricas (media móvil, tendencias) y escribe en data/processed/analytics.db.
Fail-safe: no bloquea el loop principal.
"""

import json
import logging
import sqlite3
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("data_analyzer")

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
DB_PATH = PROCESSED_DIR / "analytics.db"

# Ventana para media móvil (últimos N registros)
MOVING_AVG_WINDOW = 10

# Cache en memoria por fuente
_source_buffers: dict[str, deque] = {}
_last_processed_file: str = ""


def _init_db() -> None:
    """Crea la tabla de analytics si no existe."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            source TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL,
            moving_avg REAL,
            records_count INTEGER
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analytics_source_ts
        ON analytics(source, ts)
    """)
    conn.commit()
    conn.close()


def _get_processed_files() -> set[str]:
    """Retorna los nombres de archivo ya procesados (desde DB)."""
    conn = sqlite3.connect(str(DB_PATH))
    files = set()
    try:
        for row in conn.execute("SELECT DISTINCT source FROM analytics WHERE source LIKE '%.jsonl'"):
            files.add(row[0])
    except Exception:
        pass
    conn.close()
    return files


def _store_analytics(source: str, metric: str, value: float, avg: float, count: int) -> None:
    """Inserta una fila en analytics.db."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO analytics (ts, source, metric_name, metric_value, moving_avg, records_count) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source, metric, value, avg, count),
    )
    conn.commit()
    conn.close()


async def process_raw_files() -> None:
    """Lee data/raw/*.jsonl y computa analytics. Fails silently."""
    global _last_processed_file

    try:
        _init_db()
    except Exception as e:
        log.warning("data_analyzer: no se pudo inicializar DB: %s", e)
        return

    raw_files = sorted(RAW_DIR.glob("*.jsonl"))
    if not raw_files:
        log.debug("data_analyzer: no hay archivos raw para procesar")
        return

    for raw_path in raw_files:
        fname = raw_path.name
        # Saltar si ya se procesó este archivo en esta sesión
        if _last_processed_file and fname <= _last_processed_file:
            continue

        try:
            records = []
            with open(raw_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

            if not records:
                continue

            # Agrupar por fuente
            by_source: dict[str, list[dict]] = {}
            for r in records:
                src = r.get("source", "unknown")
                by_source.setdefault(src, []).append(r)

            for source, src_records in by_source.items():
                # Inicializar buffer si no existe
                if source not in _source_buffers:
                    _source_buffers[source] = deque(maxlen=MOVING_AVG_WINDOW)

                for rec in src_records:
                    data = rec.get("data", {})
                    latency = rec.get("latency_ms", 0)

                    # Extraer métricas numéricas del data
                    for key, val in data.items():
                        if isinstance(val, (int, float)):
                            _source_buffers[source].append(val)
                            avg = sum(_source_buffers[source]) / len(_source_buffers[source])
                            _store_analytics(source, key, float(val), round(avg, 2), len(_source_buffers[source]))

                    # Registrar también la latencia
                    if isinstance(latency, (int, float)):
                        _store_analytics(source, "latency_ms", float(latency), float(latency), 1)

            _last_processed_file = fname
            log.info("data_analyzer: procesado %s (%d registros, %d fuentes)", fname, len(records), len(by_source))

        except Exception as e:
            log.debug("data_analyzer: error en %s: %s", fname, e)


# Versión síncrona para tests
def process_raw_files_sync() -> int:
    """Versión síncrona para tests. Retorna número de registros procesados."""
    global _last_processed_file, _source_buffers

    _source_buffers = {}
    _last_processed_file = ""

    try:
        _init_db()
    except Exception:
        return 0

    total = 0
    for raw_path in sorted(RAW_DIR.glob("*.jsonl")):
        try:
            with open(raw_path) as f:
                records = [json.loads(line) for line in f if line.strip()]
        except Exception:
            continue

        if not records:
            continue

        by_source: dict[str, list[dict]] = {}
        for r in records:
            by_source.setdefault(r.get("source", "unknown"), []).append(r)

        for source, src_records in by_source.items():
            if source not in _source_buffers:
                _source_buffers[source] = deque(maxlen=MOVING_AVG_WINDOW)

            for rec in src_records:
                data = rec.get("data", {})
                latency = rec.get("latency_ms", 0)

                for key, val in data.items():
                    if isinstance(val, (int, float)):
                        _source_buffers[source].append(val)
                        avg = sum(_source_buffers[source]) / len(_source_buffers[source])
                        _store_analytics(source, key, float(val), round(avg, 2), len(_source_buffers[source]))

                if isinstance(latency, (int, float)):
                    _store_analytics(source, "latency_ms", float(latency), float(latency), 1)

            total += len(src_records)

        _last_processed_file = raw_path.name

    return total


def get_analytics_summary() -> list[dict]:
    """Retorna resumen de analytics para reportes."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT source, metric_name, AVG(metric_value), AVG(moving_avg), MAX(records_count) "
        "FROM analytics GROUP BY source, metric_name ORDER BY source"
    ).fetchall()
    conn.close()
    return [
        {"source": r[0], "metric": r[1], "avg_value": round(r[2], 2),
         "avg_moving": round(r[3], 2), "records": r[4]}
        for r in rows
    ]
