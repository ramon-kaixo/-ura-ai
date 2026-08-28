import logging
from typing import Any

log = logging.getLogger("memoria.ingesto")
PROCESADOS: set[str] = set()


def procesar_archivo(ruta: str) -> dict[str, Any] | None:
    log.warning("ingesto stub: procesar_archivo(%s) no implementado", ruta)
    return None


async def procesar_inbox_completo() -> dict[str, Any]:
    log.warning("ingesto stub: procesar_inbox_completo no implementado")
    return {"status": "stub", "procesados": 0, "errores": 0}
