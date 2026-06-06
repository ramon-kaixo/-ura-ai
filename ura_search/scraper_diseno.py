#!/usr/bin/env python3
"""scraper_diseno.py — Colector de diseño (Behance, Pinterest, GitHub).

Descarga carteles, menus, branding de fuentes de diseño.
Sin IA. Solo httpx async + parsing HTML.
"""
import argparse, asyncio, json, logging, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import httpx

BASE_DIR = Path(__file__).parent; DATA_DIR = BASE_DIR / "data"
COLA_DIR = Path.home() / ".nervioso" / "ura_search" / "cola" / "diseno"
LOG_PATH = DATA_DIR / "scraper_diseno.log"
DATA_DIR.mkdir(exist_ok=True); COLA_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("scraper_diseno")

FUENTES = {
    "behance": {"url": "https://www.behance.net/search/projects?search={query}", "tipo": "inspiracion"},
    "pinterest": {"url": "https://www.pinterest.com/search/pins/?q={query}", "tipo": "inspiracion"},
    "github_design": {"url": "https://github.com/search?q={query}+poster&type=repositories", "tipo": "recursos"},
}

CRITERIOS = ["restaurant+poster", "bar+menu+design", "food+branding", "carta+restaurante+diseno",
             "menu+tipografia", "terraza+cartel", "navarra+hosteleria+diseno"]

async def scrape_fuente(client: httpx.AsyncClient, fuente: str, query: str) -> list[dict]:
    url = FUENTES[fuente]["url"].format(query=query)
    resultados = []
    try:
        r = await client.get(url, follow_redirects=True, timeout=15)
        r.raise_for_status()
        # Extraer titulos y enlaces (basico)
        for line in r.text.split("\n"):
            if 'href="' in line and ('project' in line or 'pin' in line):
                match = re.search(r'href=["\'](/[^"\']+)["\']', line)
                title_match = re.search(r'title=["\']([^"\']+)["\']', line)
                if match:
                    resultados.append({
                        "url": f"https://www.{fuente}.com{match.group(1)}",
                        "titulo": title_match.group(1) if title_match else "",
                        "fuente": fuente,
                        "query": query,
                    })
        log.debug("  %s: %d resultados para '%s'", fuente, len(resultados), query[:30])
    except Exception as e:
        log.debug("  %s: error con '%s': %s", fuente, query[:30], e)
    return resultados

async def collect(max_items: int = 20) -> list[dict]:
    client = httpx.AsyncClient(timeout=15, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; URA-Search/1.0)"})
    todos = []
    try:
        for fuente in FUENTES:
            for query in CRITERIOS:
                r = await scrape_fuente(client, fuente, query)
                todos.extend(r)
                if len(todos) >= max_items:
                    break
            if len(todos) >= max_items:
                break
    finally:
        await client.aclose()

    # Limitar y deduplicar por URL
    vistos = set()
    unicos = []
    for item in todos[:max_items * 2]:
        if item["url"] not in vistos:
            vistos.add(item["url"])
            unicos.append(item)

    # Guardar en cola
    ts = datetime.now(timezone.utc).isoformat()
    for item in unicos[:max_items]:
        item["timestamp"] = ts
        sha = __import__("hashlib").sha256(item["url"].encode()).hexdigest()[:16]
        (COLA_DIR / f"{sha}.meta.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")

    log.info("✅ Diseño: %d/%d resultados únicos", len(unicos), len(todos))
    return unicos[:max_items]

def main():
    r = asyncio.run(collect(max_items=10))
    print(json.dumps(r, indent=2, ensure_ascii=False)[:500])

if __name__ == "__main__":
    main()
