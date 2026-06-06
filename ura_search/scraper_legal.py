#!/usr/bin/env python3
"""scraper_legal.py — Colector de normativa legal y fiscal.

Fuentes: BOE, Navarra.es, Agencia Tributaria, Sede electrónica.
Sin IA. httpx async + extracción de texto.
"""
import argparse, asyncio, json, logging, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import httpx

BASE_DIR = Path(__file__).parent; DATA_DIR = BASE_DIR / "data"
COLA_DIR = Path.home() / ".nervioso" / "ura_search" / "cola" / "legal"
LOG_PATH = DATA_DIR / "scraper_legal.log"
DATA_DIR.mkdir(exist_ok=True); COLA_DIR.mkdir(exist_ok=True, parents=True)
log = logging.getLogger("scraper_legal")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)])

URLS = [
    {"url": "https://www.boe.es/buscar/act.php?id=BOE-A-2022-5087", "fuente": "BOE", "tema": "hosteleria"},
    {"url": "https://www.boe.es/buscar/act.php?id=BOE-A-2025-1234", "fuente": "BOE", "tema": "laboral"},
    {"url": "https://www.navarra.es/es/web/turismo/restauracion", "fuente": "Navarra", "tema": "restauracion"},
    {"url": "https://www.hacienda.navarra.es/", "fuente": "Hacienda Navarra", "tema": "fiscal"},
    {"url": "https://sede.agenciatributaria.gob.es/Sede/iva.html", "fuente": "Agencia Tributaria", "tema": "iva"},
    {"url": "https://www.sepe.es/HomeSepe/Personas/contratos-trabajo", "fuente": "SEPE", "tema": "laboral"},
    {"url": "https://www.boe.es/buscar/act.php?id=BOE-A-2023-1234", "fuente": "BOE", "tema": "sanidad"},
]

async def collect(max_items: int = 10) -> list[dict]:
    client = httpx.AsyncClient(timeout=20, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; URA-Search/1.0)"})
    resultados = []
    try:
        for item in URLS[:max_items]:
            try:
                r = await client.get(item["url"], timeout=15)
                r.raise_for_status()
                # Extraer texto básico
                text = re.sub(r'<[^>]+>', ' ', r.text)
                text = re.sub(r'\s+', ' ', text)[:2000].strip()
                resultados.append({"url": item["url"], "fuente": item["fuente"], "tema": item["tema"],
                                  "contenido": text[:500], "status": r.status_code})
                log.debug("  %s: OK", item["fuente"])
            except Exception as e:
                log.debug("  %s: %s", item["fuente"], e)
    finally:
        await client.aclose()

    # Guardar en cola
    ts = datetime.now(timezone.utc).isoformat()
    for item in resultados:
        item["timestamp"] = ts
        sha = __import__("hashlib").sha256(item["url"].encode()).hexdigest()[:16]
        (COLA_DIR / f"{sha}.meta.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")

    log.info("✅ Legal: %d resultados", len(resultados))
    return resultados

if __name__ == "__main__":
    r = asyncio.run(collect())
    print(json.dumps(r, indent=2, ensure_ascii=False)[:300])
