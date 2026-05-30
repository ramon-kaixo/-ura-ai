#!/usr/bin/env python3
"""
URA Search Cache — N2 Infrastructure (Fase 1)

Cache SQLite async-safe para resultados de búsquedas.
Fingerprint SHA256(query + fechas) para anti-repetición.

Design notes:
- Uses aiosqlite for non-blocking DB I/O
- check_same_thread=False + asyncio.Lock for write safety
- Graceful degradation if aiosqlite unavailable (synchronous fallback)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

try:
    import aiosqlite  # type: ignore

    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False
    aiosqlite = None  # type: ignore

logger = logging.getLogger("ura_search_cache")

URA_DATA = Path.home() / ".ura"
DEFAULT_DB_PATH = URA_DATA / "search_cache.db"
DEFAULT_TTL_HOURS = 24


def _fingerprint(
    query: str,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    extra: str | None = None,
) -> str:
    """Generate deterministic SHA256 fingerprint for a search."""
    normalized = query.strip().lower()
    payload = f"{normalized}|{fecha_desde or ''}|{fecha_hasta or ''}|{extra or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SearchCache:
    """Async-safe SQLite cache for URA N2 search results."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS search_results (
        fingerprint TEXT PRIMARY KEY,
        query TEXT NOT NULL,
        fecha_desde TEXT,
        fecha_hasta TEXT,
        maleta_id TEXT,
        results_json TEXT NOT NULL,
        score_calidad REAL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        hits INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_expires ON search_results(expires_at);
    CREATE INDEX IF NOT EXISTS idx_maleta ON search_results(maleta_id);
    """

    def __init__(
        self, db_path: Path | None = None, default_ttl_hours: int = DEFAULT_TTL_HOURS
    ) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.default_ttl_hours = default_ttl_hours
        self._write_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Create DB directory and schema if missing. Safe to call repeatedly."""
        if self._initialized:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not HAS_AIOSQLITE:
            logger.warning("aiosqlite no disponible — cache en modo degradado (no-op)")
            self._initialized = True
            return
        async with aiosqlite.connect(self.db_path, check_same_thread=False) as db:
            await db.executescript(self._SCHEMA)
            await db.commit()
        self._initialized = True
        logger.info("SearchCache inicializado en %s", self.db_path)

    async def get(
        self,
        query: str,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
        maleta_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Return cached result if fingerprint matches and has not expired."""
        await self.initialize()
        if not HAS_AIOSQLITE:
            return None
        fp = _fingerprint(query, fecha_desde, fecha_hasta, maleta_id)
        now_iso = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.db_path, check_same_thread=False) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM search_results WHERE fingerprint = ? AND expires_at > ?",
                (fp, now_iso),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            # Increment hit counter
            await db.execute(
                "UPDATE search_results SET hits = hits + 1 WHERE fingerprint = ?", (fp,)
            )
            await db.commit()
            try:
                results = json.loads(row["results_json"])
            except json.JSONDecodeError:
                logger.error("Cache fingerprint %s tiene JSON corrupto", fp)
                return None
            return {
                "fingerprint": fp,
                "query": row["query"],
                "maleta_id": row["maleta_id"],
                "results": results,
                "score_calidad": row["score_calidad"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "hits": row["hits"] + 1,
            }

    async def put(
        self,
        query: str,
        results: list[dict[str, Any]] | dict[str, Any],
        *,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
        maleta_id: str | None = None,
        score_calidad: float = 0.0,
        ttl_hours: int | None = None,
    ) -> str:
        """Store results in cache. Returns the fingerprint."""
        await self.initialize()
        fp = _fingerprint(query, fecha_desde, fecha_hasta, maleta_id)
        if not HAS_AIOSQLITE:
            return fp
        ttl = ttl_hours if ttl_hours is not None else self.default_ttl_hours
        now = datetime.now(UTC)
        created_at = now.isoformat()
        expires_at = (now + timedelta(hours=ttl)).isoformat()
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path, check_same_thread=False) as db:
                await db.execute(
                    """
                    INSERT INTO search_results
                        (fingerprint, query, fecha_desde, fecha_hasta, maleta_id,
                         results_json, score_calidad, created_at, expires_at, hits)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(fingerprint) DO UPDATE SET
                        results_json = excluded.results_json,
                        score_calidad = excluded.score_calidad,
                        created_at = excluded.created_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        fp,
                        query,
                        fecha_desde,
                        fecha_hasta,
                        maleta_id,
                        json.dumps(results, ensure_ascii=False),
                        float(score_calidad),
                        created_at,
                        expires_at,
                    ),
                )
                await db.commit()
        logger.debug("Cache put fingerprint=%s ttl=%sh", fp, ttl)
        return fp

    async def invalidate(self, fingerprint: str) -> bool:
        """Remove a specific entry. Returns True if removed."""
        await self.initialize()
        if not HAS_AIOSQLITE:
            return False
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path, check_same_thread=False) as db:
                cursor = await db.execute(
                    "DELETE FROM search_results WHERE fingerprint = ?", (fingerprint,)
                )
                await db.commit()
                return cursor.rowcount > 0

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of rows deleted."""
        await self.initialize()
        if not HAS_AIOSQLITE:
            return 0
        now_iso = datetime.now(UTC).isoformat()
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path, check_same_thread=False) as db:
                cursor = await db.execute(
                    "DELETE FROM search_results WHERE expires_at <= ?", (now_iso,)
                )
                await db.commit()
                return cursor.rowcount

    async def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        await self.initialize()
        if not HAS_AIOSQLITE:
            return {"backend": "none", "entries": 0}
        async with aiosqlite.connect(self.db_path, check_same_thread=False) as db:
            async with db.execute(
                "SELECT COUNT(*), SUM(hits), AVG(score_calidad) FROM search_results"
            ) as cursor:
                row = await cursor.fetchone()
            total = row[0] or 0
            total_hits = row[1] or 0
            avg_score = row[2] or 0.0
        return {
            "backend": "aiosqlite",
            "db_path": str(self.db_path),
            "entries": total,
            "total_hits": total_hits,
            "avg_score": round(avg_score, 3),
        }


# Module-level singleton convenience
_cache: SearchCache | None = None


def get_search_cache(db_path: Path | None = None) -> SearchCache:
    """Return the process-wide singleton cache instance."""
    global _cache
    if _cache is None:
        _cache = SearchCache(db_path=db_path)
    return _cache
