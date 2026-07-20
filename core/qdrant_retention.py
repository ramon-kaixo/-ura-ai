"""qdrant_retention.py — Política de retención y limpieza por colección Qdrant.

Uso:
    python3 -m core.qdrant_retention                     # dry-run (reporta solo)
    python3 -m core.qdrant_retention --apply              # aplica limpieza
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime, timedelta

import httpx

log = logging.getLogger("ura.qdrant_retention")

QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")

# Política de retención por colección (días)
RETENTION_POLICY: dict[str, int] = {
    "incidente_record": 90,
    "ura_documents": 0,
    "ura_transacciones": 30,
    "ura_documents_hybrid": 0,
    "memoria_web": 180,
}


async def get_collections() -> list[str]:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{QDRANT_URL}/collections")
        r.raise_for_status()
        data = r.json()
        return [c["name"] for c in data.get("result", {}).get("collections", [])]


async def get_collection_info(collection: str) -> dict:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{QDRANT_URL}/collections/{collection}")
        r.raise_for_status()
        return r.json()


async def count_points(collection: str) -> int:
    try:
        info = await get_collection_info(collection)
        return info.get("result", {}).get("points_count", 0)
    except Exception:
        return 0


async def delete_points_before(collection: str, before_ts: str) -> int:
    """Elimina puntos con fecha_publicacion anterior a before_ts."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{QDRANT_URL}/collections/{collection}/points/delete",
            json={
                "filter": {
                    "must": [
                        {
                            "key": "fecha_publicacion",
                            "range": {"lt": before_ts},
                        },
                    ],
                },
            },
        )
        r.raise_for_status()
        result = r.json()
        return result.get("result", {}).get("status", "unknown")


async def main(dry_run: bool = True) -> dict:
    stats: dict[str, dict] = {}

    collections = await get_collections()
    log.info("Colecciones encontradas: %s", collections)

    for col in collections:
        ttl = RETENTION_POLICY.get(col, 0)
        if ttl <= 0:
            stats[col] = {"policy": "keep_all", "points": await count_points(col)}
            log.info("  %s: retención indefinida (%s puntos)", col, stats[col]["points"])
            continue

        cutoff = datetime.now(UTC) - timedelta(days=ttl)
        cutoff_ts = cutoff.isoformat()
        points_before = await count_points(col)

        if dry_run:
            stats[col] = {"policy": f"ttl={ttl}d", "points_before": points_before, "action": "dry_run"}
            log.info("  %s: TTL=%dd, puntos actuales=%d [dry-run, no se elimina]", col, ttl, points_before)
        else:
            try:
                result = await delete_points_before(col, cutoff_ts)
                points_after = await count_points(col)
                stats[col] = {
                    "policy": f"ttl={ttl}d",
                    "points_before": points_before,
                    "points_after": points_after,
                    "deleted": points_before - points_after,
                    "result": result,
                }
                log.info(
                    "  %s: eliminados %d puntos (antes=%d, después=%d)",
                    col,
                    stats[col]["deleted"],
                    points_before,
                    points_after,
                )
            except Exception as e:
                log.warning("  %s: error: %s", col, e)
                stats[col] = {"error": str(e)}

    return stats


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    dry_run = "--apply" not in sys.argv
    stats = asyncio.run(main(dry_run=dry_run))
    log.info(json.dumps(stats, indent=2))
