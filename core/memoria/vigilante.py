"""Vigilante: re-check de fuentes con cambio de contenido → versionado de ideas."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from core.mochila.tools import page_read

log = logging.getLogger("memoria.vigilante")

FUENTES_FILE = Path.home() / ".nervioso" / "fuentes_vigiladas.json"


def cargar_fuentes() -> list[dict]:
    if not FUENTES_FILE.exists():
        return []
    return json.loads(FUENTES_FILE.read_text())


def guardar_fuentes(fuentes: list[dict]) -> None:
    FUENTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    FUENTES_FILE.write_text(json.dumps(fuentes, indent=2, ensure_ascii=False))


def fuente_a_texto(pagina: dict) -> str:
    """Extrae el texto completo de una pagina leida con page_read."""
    if "content" in pagina:
        return pagina["content"]
    return ""


async def revisar_fuente(fuente: dict) -> dict:
    """Revisa una fuente. Si cambio, extrae texto nuevo. Si no, retorna estado."""
    import blake3

    url = fuente.get("url", "")
    tema = fuente.get("tema", "")
    hash_anterior = fuente.get("hash_actual", "")

    resultado = {
        "url": url,
        "cambio": False,
        "hash": hash_anterior,
        "texto": "",
        "metadatos": {},
    }

    try:
        pagina = await page_read(url, max_chars=30000)
    except Exception as e:
        log.error(f"Error leyendo {url}: {e}")
        resultado["error"] = str(e)
        return resultado

    if "error" in pagina:
        resultado["error"] = pagina["error"]
        return resultado

    contenido = fuente_a_texto(pagina)
    if not contenido:
        return resultado

    hasher = blake3.blake3()
    hasher.update(contenido.encode())
    hash_nuevo = hasher.hexdigest()

    if hash_nuevo == hash_anterior and hash_anterior:
        return resultado

    resultado["cambio"] = True
    resultado["hash"] = hash_nuevo
    resultado["texto"] = contenido
    resultado["metadatos"] = {
        "titulo": "",
        "url": url,
        "tema": tema,
    }

    fuente["hash_actual"] = hash_nuevo
    fuente["ultima_revision"] = datetime.now(timezone.utc).isoformat()

    return resultado


async def procesar_cambios() -> list[dict]:
    """Revisa todas las fuentes vigiladas. Para las que cambiaron,
    comprime y versiona las ideas via Qdrant."""
    import asyncio
    from core.memoria.compresor import comprimir_a_ideas
    from core.memoria.qdrant_store import almacenar_ideas, marcar_antiguas, _get_client
    from qdrant_client import models

    fuentes = cargar_fuentes()
    if not fuentes:
        return []

    cambios: list[dict] = []
    for fuente in fuentes:
        result = await revisar_fuente(fuente)
        if result.get("cambio"):
            cambios.append(result)

    if not cambios:
        guardar_fuentes(fuentes)
        return []

    for cambio in cambios:
        try:
            ideas = await comprimir_a_ideas(
                cambio["texto"],
                fuente=cambio["url"],
                hash_origen=cambio["hash"],
            )
            if ideas:
                marcar_antiguas(cambio["url"])
                n = await almacenar_ideas(ideas)
                cambio["ideas_insertadas"] = n
                cambio["total_ideas"] = len(ideas)
        except Exception as e:
            log.error(f"Error comprimiendo cambios de {cambio['url']}: {e}")

    guardar_fuentes(fuentes)
    return cambios
