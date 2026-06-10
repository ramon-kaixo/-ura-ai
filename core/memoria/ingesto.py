import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

import blake3

from core.memoria.detector import detectar_tipo
from core.memoria.extractores import extraer_archivo

INBOX_DIR = Path(os.environ.get("MEMORIA_INBOX", os.path.expanduser("~/.nervioso/inbox")))
CUARENTENA_DIR = Path(os.environ.get("MEMORIA_CUARENTENA", os.path.expanduser("~/.nervioso/cuarentena")))
CUARENTENA_TTL_HORAS = int(os.environ.get("MEMORIA_CUARENTENA_TTL", "24"))

PROCESADOS: set[str] = set()
log = logging.getLogger("mochila.memoria")


def hash_contenido(ruta: Path) -> str:
    hasher = blake3.blake3()
    with open(ruta, "rb") as f:
        while True:
            bloque = f.read(65536)
            if not bloque:
                break
            hasher.update(bloque)
    return hasher.hexdigest()


def mover_a_cuarentena(ruta: Path) -> Path:
    CUARENTENA_DIR.mkdir(parents=True, exist_ok=True)
    destino = CUARENTENA_DIR / f"{ruta.stem}_{int(time.time())}{ruta.suffix}"
    shutil.move(str(ruta), str(destino))
    return destino


def limpiar_cuarentena() -> int:
    if not CUARENTENA_DIR.exists():
        return 0
    ahora = time.time()
    ttl_segundos = CUARENTENA_TTL_HORAS * 3600
    eliminados = 0
    for f in CUARENTENA_DIR.iterdir():
        if f.is_file() and ahora - f.stat().st_mtime > ttl_segundos:
            f.unlink()
            eliminados += 1
    return eliminados


def procesar_archivo(ruta: Path) -> dict | None:
    try:
        h = hash_contenido(ruta)
        if h in PROCESADOS:
            limpiar_cuarentena()
            cuarentena = mover_a_cuarentena(ruta)
            log.info(f"Duplicado {ruta.name} (hash={h[:12]}...) → cuarentena/{cuarentena.name}")
            return None

        tipo = detectar_tipo(ruta)
        PROCESADOS.add(h)

        extraido = extraer_archivo(ruta, tipo)

        limpiar_cuarentena()

        return {
            "hash": h,
            "tipo": tipo,
            "ruta_original": str(ruta),
            "tamano_bytes": ruta.stat().st_size,
            "extraido": extraido,
        }
    except OSError as e:
        log.error(f"Error procesando {ruta}: {e}")
        return None


class IngestionWatcher:
    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self._stop = False

    async def run(self) -> None:
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        CUARENTENA_DIR.mkdir(parents=True, exist_ok=True)
        log.info(f"IngestionWatcher iniciado — inbox={INBOX_DIR}, cuarentena={CUARENTENA_DIR}")
        while not self._stop:
            for f in sorted(INBOX_DIR.iterdir()):
                if not f.is_file():
                    continue
                resultado = procesar_archivo(f)
                if resultado:
                    log.info(f"Nuevo archivo: {f.name} tipo={resultado['tipo']} hash={resultado['hash'][:12]}...")
            limpiar_cuarentena()
            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        self._stop = True


async def procesar_inbox_completo() -> dict:
    """Procesa todos los archivos en inbox: detect → extract → compress → Qdrant."""
    from core.memoria.compresor import comprimir_a_ideas
    from core.memoria.qdrant_store import almacenar_ideas

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    resultado = {"archivos": 0, "extraidos": 0, "ideas_total": 0, "ideas_insertadas": 0, "errores": 0}

    for f in sorted(INBOX_DIR.iterdir()):
        if not f.is_file():
            continue
        resultado["archivos"] += 1
        proc = procesar_archivo(f)
        if not proc:
            continue
        if not proc.get("extraido"):
            continue
        ex = proc["extraido"]
        texto = ex.get("texto_plano", "")
        if not texto:
            continue
        resultado["extraidos"] += 1

        try:
            fuente = ex.get("metadatos", {}).get("url", "") or f"file://{proc['ruta_original']}"
            ideas = await comprimir_a_ideas(texto, fuente=fuente, hash_origen=proc["hash"])
            if ideas:
                n = await almacenar_ideas(ideas)
                resultado["ideas_total"] += len(ideas)
                resultado["ideas_insertadas"] += n
        except Exception as e:
            log.error(f"Error comprimiendo {f.name}: {e}")
            resultado["errores"] += 1

    return resultado
