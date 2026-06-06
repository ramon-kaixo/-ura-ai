#!/usr/bin/env python3
"""StateManager — almacenamiento con fallback en cadena: Redis → SQLite → JSON.

Capa de estado compartido para el ecosistema URA.
Sigue el patrón Crew Chief: si un backend cae, el siguiente asume.
"""

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

log = logging.getLogger(__name__)

_REDIS_DEFAULTS = {"host": "127.0.0.1", "port": 6379, "db": 0, "decode_responses": True}
_SQLITE_PATH = Path("/tmp/ura_state.sqlite")
_JSON_PATH = Path("/tmp/ura_state.json")
_RECONNECT_DELAY = 30


class StateManager:
    """Gestor de estado con failover automático Redis → SQLite → JSON.

    Uso:
        sm = StateManager()
        await sm.set("procesos:router", {"status": "ok"})
        val = await sm.get("procesos:router")
    """

    def __init__(self, redis_config: dict[str, Any] | None = None) -> None:
        self._redis_config = redis_config or _REDIS_DEFAULTS
        self._redis: Any = None
        self._sqlite_conn: sqlite3.Connection | None = None
        self._active_backend: str = "none"

    # ── Arranque --------------------------------------------------------

    async def start(self) -> None:
        """Inicializa los backends en orden de preferencia."""
        await self._try_redis()
        if self._active_backend == "none":
            self._try_sqlite()
        if self._active_backend == "none":
            self._try_json()
        log.info("StateManager activo con backend: %s", self._active_backend)

    async def stop(self) -> None:
        if self._redis:
            await self._redis.aclose()
        if self._sqlite_conn:
            self._sqlite_conn.close()

    # ── API pública -----------------------------------------------------

    async def get(self, key: str) -> Any | None:
        for attempt in range(3):
            try:
                return await self._do_get(key)
            except ConnectionError:
                await self._fallback()
                continue
        log.error("StateManager.get(%s): todos los backends fallaron", key)
        return None

    async def set(self, key: str, value: Any) -> bool:
        for attempt in range(3):
            try:
                return await self._do_set(key, value)
            except ConnectionError:
                await self._fallback()
                continue
        log.error("StateManager.set(%s): todos los backends fallaron", key)
        return False

    async def delete(self, key: str) -> bool:
        for attempt in range(3):
            try:
                return await self._do_delete(key)
            except ConnectionError:
                await self._fallback()
                continue
        return False

    async def health(self) -> dict[str, Any]:
        return {
            "active_backend": self._active_backend,
            "redis_connected": self._redis is not None,
            "sqlite_connected": self._sqlite_conn is not None,
            "json_path": str(_JSON_PATH),
        }

    # ── Backend Redis ---------------------------------------------------

    async def _try_redis(self) -> None:
        if aioredis is None:
            return
        try:
            self._redis = aioredis.Redis(**self._redis_config)
            await self._redis.ping()
            self._active_backend = "redis"
            log.info("Redis conectado en %s:%s", self._redis_config["host"], self._redis_config["port"])
        except Exception as e:
            log.warning("Redis no disponible (%s), siguiente backend...", e)
            self._redis = None

    async def _redis_get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def _redis_set(self, key: str, value: Any) -> bool:
        await self._redis.set(key, json.dumps(value))
        return True

    async def _redis_delete(self, key: str) -> bool:
        return bool(await self._redis.delete(key))

    # ── Backend SQLite --------------------------------------------------

    def _try_sqlite(self) -> None:
        try:
            _SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._sqlite_conn = sqlite3.connect(str(_SQLITE_PATH))
            self._sqlite_conn.execute(
                "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT, updated REAL)"
            )
            self._sqlite_conn.commit()
            self._active_backend = "sqlite"
            log.info("SQLite activo en %s", _SQLITE_PATH)
        except Exception as e:
            log.warning("SQLite no disponible (%s)", e)
            self._sqlite_conn = None

    def _sqlite_get(self, key: str) -> Any | None:
        cur = self._sqlite_conn.execute("SELECT value FROM state WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def _sqlite_set(self, key: str, value: Any) -> bool:
        self._sqlite_conn.execute(
            "INSERT OR REPLACE INTO state (key, value, updated) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self._sqlite_conn.commit()
        return True

    def _sqlite_delete(self, key: str) -> bool:
        cur = self._sqlite_conn.execute("DELETE FROM state WHERE key = ?", (key,))
        self._sqlite_conn.commit()
        return cur.rowcount > 0

    # ── Backend JSON ----------------------------------------------------

    def _try_json(self) -> None:
        try:
            _JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
            if not _JSON_PATH.exists():
                _JSON_PATH.write_text("{}")
            self._active_backend = "json"
            log.info("JSON activo en %s", _JSON_PATH)
        except Exception as e:
            log.error("JSON no disponible (%s) — SIN ESTADO", e)

    def _json_get(self, key: str) -> Any | None:
        data = json.loads(_JSON_PATH.read_text())
        return data.get(key)

    def _json_set(self, key: str, value: Any) -> bool:
        data = json.loads(_JSON_PATH.read_text())
        data[key] = value
        _JSON_PATH.write_text(json.dumps(data, indent=2))
        return True

    def _json_delete(self, key: str) -> bool:
        data = json.loads(_JSON_PATH.read_text())
        if key not in data:
            return False
        del data[key]
        _JSON_PATH.write_text(json.dumps(data, indent=2))
        return True

    # ── Internas --------------------------------------------------------

    async def _do_get(self, key: str) -> Any:
        if self._active_backend == "redis" and self._redis:
            return await self._redis_get(key)
        if self._active_backend == "sqlite" and self._sqlite_conn:
            return self._sqlite_get(key)
        return self._json_get(key)

    async def _do_set(self, key: str, value: Any) -> bool:
        if self._active_backend == "redis" and self._redis:
            return await self._redis_set(key, value)
        if self._active_backend == "sqlite" and self._sqlite_conn:
            return self._sqlite_set(key, value)
        return self._json_set(key, value)

    async def _do_delete(self, key: str) -> bool:
        if self._active_backend == "redis" and self._redis:
            return await self._redis_delete(key)
        if self._active_backend == "sqlite" and self._sqlite_conn:
            return self._sqlite_delete(key)
        return self._json_delete(key)

    async def _fallback(self) -> None:
        log.warning("Fallback desde %s al siguiente backend", self._active_backend)
        if self._active_backend == "redis":
            self._try_sqlite()
        elif self._active_backend == "sqlite":
            self._try_json()
        if self._active_backend == "none":
            self._try_json()
