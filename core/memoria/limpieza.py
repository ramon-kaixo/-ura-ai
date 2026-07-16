"""Limpieza automatica: inbox, cuarentena, versiones antiguas en Qdrant."""

import logging
import time
from pathlib import Path

from core.memoria.qdrant_store import _get_client
from qdrant_client import models

INBOX = Path.home() / ".nervioso" / "inbox"
CUARENTENA = Path.home() / ".nervioso" / "cuarentena"
COLLECTION = "ideas"

log = logging.getLogger("memoria.limpieza")


def limpiar_inbox(ttl_horas: int = 24) -> int:
    if not INBOX.exists():
        return 0
    ahora = time.time()
    ttl = ttl_horas * 3600
    eliminados = 0
    for f in INBOX.iterdir():
        if f.is_file() and ahora - f.stat().st_mtime > ttl:
            f.unlink()
            eliminados += 1
    return eliminados


def limpiar_cuarentena(ttl_horas: int = 24) -> int:
    if not CUARENTENA.exists():
        return 0
    ahora = time.time()
    ttl = ttl_horas * 3600
    eliminados = 0
    for f in CUARENTENA.iterdir():
        if f.is_file() and ahora - f.stat().st_mtime > ttl:
            f.unlink()
            eliminados += 1
    return eliminados


def limpiar_versiones_antiguas(keep: int = 3) -> int:
    """Mantiene solo las `keep` versiones mas recientes de cada fuente.
    Las ideas con vigente=false y version baja se eliminan."""
    client = _get_client()
    eliminados = 0
    offset = None
    while True:
        items, next_offset = client.scroll(
            COLLECTION,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="vigente", match=models.MatchValue(value=False))]
            ),
            limit=100,
            offset=offset,
            with_payload=["fuente", "version", "fecha_captura"],
            with_vectors=False,
        )
        for point in items:
            payload = point.payload or {}
            version = payload.get("version", 1)
            if isinstance(version, int) and version <= 1:
                client.delete(COLLECTION, [point.id])
                eliminados += 1
        if next_offset is None or not items:
            break
        offset = next_offset
    if eliminados:
        log.info(f"Limpieza Qdrant: {eliminados} versiones antiguas eliminadas")
    return eliminados


def limpiar_todo(inbox_ttl: int = 24, cuarentena_ttl: int = 24) -> dict:
    return {
        "inbox": limpiar_inbox(inbox_ttl),
        "cuarentena": limpiar_cuarentena(cuarentena_ttl),
        "versiones": limpiar_versiones_antiguas(),
    }
