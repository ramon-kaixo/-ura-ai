#!/usr/bin/env python3
"""auto_reindex.py — Re-indexa documentos stale en Qdrant usando upsert atómico.

Sin delete previo: el doc_id determinista SHA-256 permite upsert directo.
Si la descarga falla, el conocimiento original se conserva intacto.

Uso:
  python3 -m core.auto_reindex              # dry-run (default)
  python3 -m core.auto_reindex --execute    # reindexa realmente
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx

from core.chunking import chunk_semantic
from core.document_quality import (
    content_type as detect_content_type,
)
from core.document_quality import (
    detect_language,
    doc_id_from_text,
    extract_publication_date,
    source_reliability,
)
from core.stealth_fetcher import fetch_stealth
from motor.core.config import UraConfig
from motor.core.qdrant_client import QdrantClient

log = logging.getLogger("ura.auto_reindex")

COLLECTION = "memoria_web"
CUTOFF_DAYS = 30
BATCH_SIZE = 100

QDRANT_BASE = "http://127.0.0.1:6333"


async def _find_stale_docs_rest(qdrant, cutoff_days: int = CUTOFF_DAYS) -> list:
    """REST fallback for find_stale_docs using HTTP API."""
    cutoff = (datetime.now(UTC) - timedelta(days=cutoff_days)).isoformat()
    all_stale = []
    offset: int | None = None

    while True:
        try:
            params = {
                "limit": BATCH_SIZE,
                "filter": {
                    "must": [
                        {
                            "key": "fecha_publicacion",
                            "range": {"lt": cutoff},
                        },
                    ],
                },
                "with_payload": True,
            }
            if offset is not None:
                params["offset"] = offset

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{QDRANT_BASE}/collections/{COLLECTION}/points/scroll",
                    json=params,
                )
                resp.raise_for_status()
                data = resp.json()
                points = data.get("result", {}).get("points", [])

            if not points:
                break

            # Convert REST response to dict format (point-like with .payload key)
            for p in points:
                all_stale.append({"payload": p.get("payload", {}), "id": p.get("id")})  # noqa: PERF401

            if len(points) < BATCH_SIZE:
                break
            offset = points[-1].get("id")
        except Exception as e:
            log.warning("REST scroll falló: %s", e)
            break

    return all_stale


async def find_stale_docs(cutoff_days: int = CUTOFF_DAYS) -> list:
    qdrant = QdrantClient.instancia(UraConfig.load())
    if not qdrant.disponible:
        return []

    if getattr(qdrant, "_modo_rest", False):
        log.info("find_stale_docs using REST fallback")
        return await _find_stale_docs_rest(qdrant, cutoff_days)

    cutoff = (datetime.now(UTC) - timedelta(days=cutoff_days)).isoformat()
    all_stale = []
    offset = None

    try:
        from qdrant_client.http import models

        while True:
            scroll_result = qdrant._cliente.scroll(  # noqa: SLF001
                collection_name=COLLECTION,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="fecha_publicacion",
                            range=models.Range(lt=cutoff),
                        ),
                    ],
                ),
                limit=BATCH_SIZE,
                offset=offset,
                with_payload=True,
            )
            points = scroll_result[0] if scroll_result else []
            all_stale.extend(points)
            if len(points) < BATCH_SIZE:
                break
            if points:
                offset = points[-1].id
        return all_stale
    except Exception as e:
        log.warning("Error finding stale docs: %s", e)
        return []


async def fetch_safe(url: str, timeout: int = 30) -> tuple[str | None, bool]:  # noqa: ASYNC109
    try:
        html = await fetch_stealth(url, timeout=timeout)
        if html and len(html) > 50:
            return html, True
        return None, False
    except Exception as e:
        log.debug("Fetch failed for %s: %s", url, e)
        return None, False


async def atomic_upsert(html: str, url: str) -> bool:
    qdrant = QdrantClient.instancia(UraConfig.load())
    if not qdrant.disponible:
        return False

    text = html
    chunks = chunk_semantic(text)
    if not chunks:
        return False

    idioma = detect_language(text)
    fiabilidad = source_reliability(url) if url else 0.5
    fecha_pub = extract_publication_date(text) or datetime.now(UTC).isoformat()
    tipo_contenido = detect_content_type(text)
    ahora = datetime.now(UTC).isoformat()

    docs = []
    for i, chunk in enumerate(chunks):
        doc_id = doc_id_from_text(chunk, prefix="mem")
        metadata = {
            "fuente": url,
            "source": url,
            "fecha_descarga": ahora,
            "fecha_publicacion": fecha_pub,
            "tipo": "html",
            "tipo_contenido": tipo_contenido,
            "idioma": idioma,
            "fiabilidad": fiabilidad,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "texto_completo": chunk[:2000],
        }
        docs.append((doc_id, chunk, metadata))

    guardados = qdrant.guardar_documentos_batch(docs, COLLECTION)
    return guardados > 0


async def reindex_stale(dry_run: bool = True) -> dict:  # noqa: FBT001, FBT002
    stale = await find_stale_docs()
    stats = {"found": len(stale), "reindexed": 0, "failed": 0, "skipped": 0}

    for point in stale:
        url = point.payload.get("fuente") or point.payload.get("source")
        if not url:
            stats["skipped"] += 1
            continue

        if dry_run:
            continue

        html, ok = await fetch_safe(url)
        if not ok:
            stats["failed"] += 1
            continue

        success = await atomic_upsert(html, url)
        if success:
            stats["reindexed"] += 1
        else:
            stats["failed"] += 1

    return stats


def main() -> None:
    import sys

    dry_run = "--execute" not in sys.argv
    stats = asyncio.run(reindex_stale(dry_run=dry_run))
    log.info(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
