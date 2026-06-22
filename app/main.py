#!/usr/bin/env python3
"""main.py — Orquestador principal del sistema URA."""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path


from app.capturador import CapturadorTarget
from app.gestor_archivos import GestorArchivosSeguro

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPORTS = Path.home() / "URA" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

class Orquestador:
    def __init__(self) -> None:
        self.capturador = CapturadorTarget()
        self.gestor = GestorArchivosSeguro()

    async def ciclo(self) -> dict:
        logger.info("Ciclo de orquestacion")
        r = {"timestamp": datetime.now().isoformat(), "acciones": [], "errores": [], "estado": "OK"}
        try:
            captura = self.capturador.capturar()
            if captura: r["acciones"].append("captura_ok")
        except Exception as e:
            r["errores"].append(str(e))
        try:
            cola = self.gestor.archivos_en_cola()
            r["cola"] = cola
        except Exception as e:
            r["errores"].append(str(e))
        path = REPORTS / f"orquestacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(r, indent=2))
        return r

async def main():
    o = Orquestador()
    r = await o.ciclo()
    print(json.dumps(r, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
