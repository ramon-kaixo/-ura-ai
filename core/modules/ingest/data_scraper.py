#!/usr/bin/env python3
"""data_scraper.py — Recolector asíncrono de datos externos vía API JSON.

Corrutina #16 del ura-supervisor. Obtiene datos de una API pública,
los persiste en data/raw/data_YYYY-MM-DD.jsonl.

Fail-safe: Si la red falla, se silencia y reintenta en el próximo ciclo.
"""

import json
import logging
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("data_scraper")

# APIs públicas sin API key requerida
ENDPOINTS = [
    {
        "name": "coingecko_btc",
        "url": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
        "parser": lambda d: {
            "btc_usd": d.get("bitcoin", {}).get("usd", 0),
            "eth_usd": d.get("ethereum", {}).get("usd", 0),
        },
    },
    {
        "name": "httpbin_ip",
        "url": "https://httpbin.org/ip",
        "parser": lambda d: {"origin": d.get("origin", "?")},
    },
]

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _today_path() -> Path:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return DATA_DIR / f"data_{date_str}.jsonl"


async def collect_snapshot() -> None:
    """Ejecuta una ronda de recolección contra todos los endpoints.

    Fails silently — nunca lanza excepciones al event loop.
    """
    _ensure_dir()
    path = _today_path()
    results: list[dict] = []

    for ep in ENDPOINTS:
        try:
            t0 = time.monotonic()
            req = urllib.request.Request(ep["url"], headers={"User-Agent": "URA/2.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read())
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            parsed = ep["parser"](raw)
            results.append({
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": ep["name"],
                "data": parsed,
                "latency_ms": elapsed_ms,
            })
            log.debug("data_scraper: %s OK (%dms)", ep["name"], elapsed_ms)
        except Exception as e:
            log.debug("data_scraper: %s falló: %s", ep["name"], e)

    if results:
        try:
            with open(path, "a") as f:
                for r in results:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception as e:
            log.warning("data_scraper: error escribiendo a %s: %s", path, e)


# Versión síncrona para tests
def collect_snapshot_sync() -> list[dict]:
    """Versión síncrona para tests unitarios. Retorna los datos recolectados."""
    _ensure_dir()
    path = _today_path()
    results: list[dict] = []

    for ep in ENDPOINTS:
        try:
            t0 = time.monotonic()
            req = urllib.request.Request(ep["url"], headers={"User-Agent": "URA/2.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read())
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            parsed = ep["parser"](raw)
            entry = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": ep["name"],
                "data": parsed,
                "latency_ms": elapsed_ms,
            }
            results.append(entry)
            with open(path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            log.debug("data_scraper: %s falló: %s", ep["name"], e)

    return results
