#!/usr/bin/env python3
"""Watchdog de inbox: detecta archivos nuevos y los envía al pipeline.
Reemplaza al webhook de n8n mientras n8n no tenga API key configurada."""
import asyncio
import hashlib
import logging
import sys
import time
from pathlib import Path

import httpx

MOCHILA = "http://127.0.0.1:4098"
INBOX = Path.home() / ".nervioso" / "inbox"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [watch] %(message)s")
log = logging.getLogger()


def hash_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest() if path.exists() else ""


async def process_file(path: Path) -> bool:
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{MOCHILA}/memoria/ingestar")
        if resp.status_code == 200:
            data = resp.json()
            ideas = data.get("ideas_insertadas", 0)
            log.info(f"{path.name} → {ideas} ideas")
            return True
        else:
            log.warning(f"{path.name} → HTTP {resp.status_code}")
            return False
    except Exception as e:
        log.error(f"{path.name}: {e}")
        return False


async def watch_loop(interval: float = 10.0):
    INBOX.mkdir(parents=True, exist_ok=True)
    seen: dict[str, str] = {}

    log.info(f"Watchdog iniciado — inbox={INBOX}")
    while True:
        for f in sorted(INBOX.iterdir()):
            if not f.is_file():
                continue
            h = hash_file(f)
            prev = seen.get(f.name, "")
            if h != prev or prev == "":
                seen[f.name] = h
                if prev == "":
                    log.info(f"Nuevo archivo: {f.name} ({f.stat().st_size} bytes)")
                    await process_file(f)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(watch_loop())
