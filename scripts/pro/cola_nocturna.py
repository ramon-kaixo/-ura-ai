#!/usr/bin/env python3
"""Cola nocturna: procesa archivos acumulados en inbox durante la noche."""
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/ramon/URA/ura_ia_1972")

from core.memoria.ingesto import procesar_inbox_completo, PROCESADOS
from core.memoria.limpieza import limpiar_todo

INBOX = Path.home() / ".nervioso" / "inbox"
PARTE_DIR = Path.home() / ".nervioso" / "partes"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [cola] %(message)s")
log = logging.getLogger()


async def main():
    PARTE_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    PROCESADOS.clear()

    archivos = list(INBOX.glob("*")) if INBOX.exists() else []
    log.info(f"Cola nocturna: {len(archivos)} archivos en inbox")

    if not archivos:
        log.info("Nada que procesar")
        return 0

    resultado = await procesar_inbox_completo()

    clean = limpiar_todo()

    elapsed = time.time() - t0
    parte = {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "archivos_en_inbox": len(archivos),
        "extraidos": resultado["extraidos"],
        "ideas_generadas": resultado["ideas_total"],
        "ideas_insertadas": resultado["ideas_insertadas"],
        "errores": resultado["errores"],
        "tiempo_total_s": round(elapsed, 1),
        "limpieza": clean,
    }

    ts = time.strftime("%Y%m%d_%H%M%S")
    import json
    parte_path = PARTE_DIR / f"cola_{ts}.json"
    parte_path.write_text(json.dumps(parte, indent=2, ensure_ascii=False))

    log.info(f"Parte: {json.dumps(parte, ensure_ascii=False)}")
    log.info(f"Completado en {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
