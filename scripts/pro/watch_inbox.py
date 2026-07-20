#!/usr/bin/env python3
"""Watchdog de inbox: detecta archivos nuevos → ingestar con retry + backoff."""

import asyncio
import hashlib
import logging
from pathlib import Path

import httpx

MOCHILA = "http://127.0.0.1:4098"
INBOX = Path.home() / ".nervioso" / "inbox"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [watch] %(message)s")
log = logging.getLogger()

MAX_RETRIES = 3
BACKOFF_BASE = 2


def hash_file(path: Path) -> str:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()  # noqa: S324
    except OSError:
        return ""


async def _check_mochila_alive() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{MOCHILA}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def process_file(path: Path) -> bool:
    if not await _check_mochila_alive():
        log.warning("Mochila no responde — esperando...")
        await asyncio.sleep(30)
        if not await _check_mochila_alive():
            log.error("Mochila sigue sin responder — saltando ciclo")
            return False

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{MOCHILA}/memoria/ingestar")

            if resp.status_code == 200:
                data = resp.json()
                ideas = data.get("ideas_insertadas", 0)
                archivos = data.get("archivos", 0)
                errores = data.get("errores", 0)
                if errores:
                    log.info(f"{path.name} → {ideas} ideas, {errores} errores")
                else:
                    log.info(f"{path.name} → {ideas} ideas [{archivos} archivos]")
                return True

            if resp.status_code == 503:
                log.warning(f"{path.name} → breaker OPEN (intento {attempt}/{MAX_RETRIES})")
                await asyncio.sleep(BACKOFF_BASE**attempt)
                continue

            if resp.status_code == 429:
                log.warning(f"{path.name} → rate limit (intento {attempt}/{MAX_RETRIES})")
                await asyncio.sleep(BACKOFF_BASE**attempt * 2)
                continue

            last_error = f"HTTP {resp.status_code}"
            log.warning(f"{path.name} → {last_error} (intento {attempt}/{MAX_RETRIES})")

        except httpx.TimeoutException:
            last_error = "timeout"
            log.warning(f"{path.name} → timeout (intento {attempt}/{MAX_RETRIES})")
        except Exception as e:
            last_error = str(e)[:80]
            log.warning(f"{path.name} → {last_error} (intento {attempt}/{MAX_RETRIES})")

        if attempt < MAX_RETRIES:
            await asyncio.sleep(BACKOFF_BASE**attempt)

    log.error(f"{path.name} → AGOTADOS {MAX_RETRIES} intentos: {last_error}")
    return False


async def watch_loop(interval: float = 10.0) -> None:
    INBOX.mkdir(parents=True, exist_ok=True)
    seen: dict[str, str] = {}

    mochila_ok = await _check_mochila_alive()
    log.info(f"Watchdog iniciado — inbox={INBOX}, mochila={'OK' if mochila_ok else 'DOWN'}")

    while True:
        for f in sorted(INBOX.iterdir()):
            if not f.is_file():
                continue
            h = hash_file(f)
            prev = seen.get(f.name, "")
            if h != prev or prev == "":
                seen[f.name] = h
                if prev == "":
                    log.info(f"Nuevo: {f.name} ({f.stat().st_size}B)")
                    await process_file(f)

        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(watch_loop())
