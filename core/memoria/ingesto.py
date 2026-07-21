import logging

log = logging.getLogger("memoria.ingesto")
PROCESADOS: set = set()
procesados_local = PROCESADOS  # alias para import en consulta.py


def procesar_archivo(ruta) -> dict | None:
    log.warning("ingesto stub: procesar_archivo(%s) no implementado", ruta)
    return None


async def procesar_inbox_completo() -> dict:
    log.warning("ingesto stub: procesar_inbox_completo no implementado")
    return {"status": "stub", "procesados": 0, "errores": 0}
