#!/usr/bin/env python3
"""Runner diario del Vigilante: revisa fuentes, comprime cambios, limpia."""
import asyncio
import logging
import sys

sys.path.insert(0, "/home/ramon/URA/ura_ia_1972")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from core.memoria.vigilante import procesar_cambios
from core.memoria.limpieza import limpiar_todo
from core.memoria.ingesto import limpiar_cuarentena


async def main():
    logging.info("Vigilante: iniciando revision...")
    cambios = await procesar_cambios()
    for c in cambios:
        logging.info(f"  Cambio: {c['url'][:80]} → {c.get('total_ideas',0)} ideas ({c.get('ideas_insertadas',0)} nuevas)")

    logging.info("Limpieza: ejecutando...")
    clean = limpiar_todo()
    logging.info(f"  inbox={clean['inbox']} cuarentena={clean['cuarentena']} versiones={clean['versiones']}")

    logging.info("Vigilante: completado")


if __name__ == "__main__":
    asyncio.run(main())
