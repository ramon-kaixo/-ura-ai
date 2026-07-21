#!/usr/bin/env python3
"""secretario_cache.py — Cliente ligero desde Mac hacia ASUS para embedding + cache.
- Envía RAW a ASUS /v2/interact para embedding (proxy)
- LRU cache local de últimas 20 interacciones
- Consultas read-only a Qdrant en ASUS vía REST.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections import OrderedDict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.interfaces import IConfigProvider

ASUS_EXEC_URL = os.environ.get("ASUS_EXEC_URL", "http://10.164.1.99:4096")


def _load_config(config: IConfigProvider | None = None) -> tuple[str, int]:
    if config is not None:
        return config.qdrant_host or os.environ.get("URA_QDRANT_HOST", "10.164.1.99"), config.qdrant_port or int(
            os.environ.get("URA_QDRANT_PORT", "6333")
        )
    try:
        from motor.core.config import UraConfig

        c = UraConfig.load()
        return c.qdrant_host or os.environ.get("URA_QDRANT_HOST", "10.164.1.99"), c.qdrant_port or int(
            os.environ.get("URA_QDRANT_PORT", "6333")
        )
    except Exception:
        return os.environ.get("URA_QDRANT_HOST", "10.164.1.99"), int(os.environ.get("URA_QDRANT_PORT", "6333"))


LRU_MAX = 20


class SecretarioCache:
    def __init__(self, config: IConfigProvider | None = None) -> None:
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._config = config

    def _qdrant_host(self) -> str:
        return _load_config(self._config)[0]

    def _qdrant_port(self) -> int:
        return _load_config(self._config)[1]

    def interact(self, raw: str, structure: dict | None = None) -> dict:
        """Envía interacción a ASUS /v2/interact y cachea el resultado."""
        cache_key = hash(raw) ^ hash(json.dumps(structure or {}, sort_keys=True))
        cache_key = str(cache_key)
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        payload = {
            "id": f"mac_{datetime.now(UTC).timestamp()}",
            "raw": raw,
            "structure": structure
            or {"intent": "consulta", "complexity": "simple", "domain": "general", "entities": []},
        }
        try:
            req = urllib.request.Request(  # noqa: S310
                f"{ASUS_EXEC_URL}/v2/interact",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                result = json.loads(resp.read().decode())
        except Exception as e:
            result = {"error": str(e), "validation": {"ok": False, "alert": True}}

        self._put_cache(cache_key, result)
        return result

    def _put_cache(self, key: str, value: dict) -> None:
        if len(self._cache) >= LRU_MAX:
            self._cache.popitem(last=False)
        self._cache[key] = value

    def buscar_qdrant(self, coleccion: str, limit: int = 10) -> list:
        """Consulta read-only a Qdrant en ASUS vía REST."""
        try:
            url = f"http://{self._qdrant_host()}:{self._qdrant_port()}/collections/{coleccion}/points/scroll"
            req = urllib.request.Request(  # noqa: S310
                url,
                data=json.dumps({"limit": limit}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                data = json.loads(resp.read().decode())
                return [p.get("payload", {}) for p in data.get("result", {}).get("points", [])]
        except Exception as e:
            return [{"error": str(e)}]

    def limpiar_cache(self) -> None:
        self._cache.clear()

    def estado(self) -> dict:
        return {
            "cache_size": len(self._cache),
            "cache_max": LRU_MAX,
            "asus_url": ASUS_EXEC_URL,
            "qdrant": f"{self._qdrant_host()}:{self._qdrant_port()}",
        }


if __name__ == "__main__":
    import sys

    sc = SecretarioCache()
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        pass
    elif len(sys.argv) > 1 and sys.argv[1] == "query":
        coleccion = sys.argv[2] if len(sys.argv) > 2 else "ura_documents"
    else:
        pass
