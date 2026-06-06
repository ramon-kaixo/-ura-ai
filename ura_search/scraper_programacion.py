#!/usr/bin/env python3
"""scraper_programacion.py — Colector de documentación técnica.

Fuentes: Python docs, Real Python, GitHub trending, Arxiv, Hugging Face.
Sin IA. httpx async + parsing HTML básico.
"""
import argparse, asyncio, json, logging, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import httpx

BASE_DIR = Path(__file__).parent; DATA_DIR = BASE_DIR / "data"
COLA_DIR = Path.home() / ".nervioso" / "ura_search" / "cola" / "programacion"
LOG_PATH = DATA_DIR / "scraper_programacion.log"
DATA_DIR.mkdir(exist_ok=True); COLA_DIR.mkdir(exist_ok=True, parents=True)
log = logging.getLogger("scraper_programacion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)])

FUENTES = {
    "python_docs": {"base": "https://docs.python.org/3.12/library/", "temas": ["asyncio", "sqlite3", "json", "pathlib", "re", "logging", "argparse", "subprocess"]},
    "realpython": {"base": "https://realpython.com/", "temas": ["python-async", "python-httpx", "python-sqlite", "python-docker", "python-api"]},
    "github_trending": {"base": "https://github.com/trending/python?since=weekly", "temas": [""]},
    "arxiv": {"base": "https://arxiv.org/search/?query=large+language+model&searchtype=all", "temas": [""]},
}

async def collect(max_items: int = 15) -> list[dict]:
    client = httpx.AsyncClient(timeout=15, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; URA-Search/1.0)"})
    resultados = []
    try:
        for fuente, config in FUENTES.items():
            for tema in config["temas"]:
                url = f"{config['base']}{tema}" if tema else config["base"]
                try:
                    r = await client.get(url, timeout=10)
                    r.raise_for_status()
                    # Extraer titulos de enlaces
                    for line in r.text.split("\n"):
                        m = re.search(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', line)
                        if m and len(m.group(2)) > 10 and len(m.group(2)) < 100:
                            resultados.append({"url": m.group(1) if m.group(1).startswith("http") else config["base"] + m.group(1).lstrip("/"),
                                              "titulo": m.group(2).strip(), "fuente": fuente, "tema": tema})
                    log.debug("  %s: OK", fuente)
                except Exception as e:
                    log.debug("  %s: %s", fuente, e)
                if len(resultados) >= max_items * 2:
                    break
            if len(resultados) >= max_items * 2:
                break
    finally:
        await client.aclose()

    # Guardar en cola
    ts = datetime.now(timezone.utc).isoformat()
    for item in resultados[:max_items]:
        item["timestamp"] = ts
        sha = __import__("hashlib").sha256(item["url"].encode()).hexdigest()[:16]
        (COLA_DIR / f"{sha}.meta.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")

    log.info("✅ Programación: %d resultados", min(len(resultados), max_items))
    return resultados[:max_items]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = asyncio.run(collect(max_items=10))
    print(json.dumps(r, indent=2, ensure_ascii=False)[:300])
