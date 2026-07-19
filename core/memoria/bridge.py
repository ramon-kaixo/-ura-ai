"""Puente entre la Mochila (busqueda web) y la Memoria (pipeline de ingesta).

web_search → page_read → guardar en inbox → procesar.
"""

import asyncio
import logging
import time
from pathlib import Path

from core.memoria.ingesto import procesar_archivo
from core.mochila.tools import page_read, web_search

INBOX = Path.home() / ".nervioso" / "inbox"
log = logging.getLogger("mochila.bridge")


async def buscar_y_aprender(query: str, max_resultados: int = 3, max_chars_pagina: int = 30000) -> list[dict]:
    """Busca en internet, descarga paginas, las guarda en inbox y las procesa."""
    resultados = []

    search_result = await web_search(query, max_resultados)
    if "error" in search_result:
        log.warning(f"Search error: {search_result['error']}")
        return resultados

    for item in search_result.get("results", []):
        url = item.get("url", "")
        title = item.get("title", "")
        if not url:
            continue

        try:
            page = await page_read(url, max_chars_pagina)
        except Exception as e:
            log.warning(f"page_read error {url}: {e}")
            continue

        if "error" in page:
            log.warning(f"Page error {url}: {page['error']}")
            continue

        guardar = _guardar_en_inbox(url, title, page.get("content", ""))
        if not guardar:
            continue

        resultado = {
            "fuente": url,
            "titulo": title,
            "snippet": item.get("snippet", ""),
            "archivo_inbox": str(guardar),
            "procesado": None,
        }

        procesado = procesar_archivo(guardar) if guardar.exists() else None
        if procesado and procesado.get("extraido"):
            resultado["procesado"] = {
                "hash": procesado["hash"],
                "tipo": procesado["tipo"],
                "metadatos": procesado["extraido"].get("metadatos", {}),
                "texto_longitud": len(procesado["extraido"].get("texto_plano", "")),
            }

        resultados.append(resultado)
        await asyncio.sleep(1)  # rate limit between requests

    return resultados


def _guardar_en_inbox(url: str, title: str, content: str) -> Path | None:
    try:
        INBOX.mkdir(parents=True, exist_ok=True)
        slug = url.rsplit("//", maxsplit=1)[-1].split("?", maxsplit=1)[0].replace("/", "_")[:80] or "pagina"
        nombre = f"{slug}_{int(time.time())}.html"
        ruta = INBOX / nombre

        html = f"""<html>
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
<pre>{content}</pre>
</body>
</html>"""
        ruta.write_text(html, encoding="utf-8")
        return ruta
    except OSError as e:
        log.exception(f"Error guardando {url}: {e}")
        return None
