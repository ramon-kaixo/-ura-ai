#!/usr/bin/env python3
"""motor_flujo.py — Motor de flujo con control de RAM y spool en disco."""

from __future__ import annotations

import asyncio
import gc
import json
import logging
from pathlib import Path

import psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MotorFlujo")

SPOOL_DIR = str(Path.home() / "URA" / "storage" / "spool")


class ControladorMemoria:
    """Componente 1: Evalua la salud del hardware."""

    def __init__(self, umbral_ram_pct: float = 85.0) -> None:
        self.umbral_ram_pct = umbral_ram_pct

    def tiene_luz_verde(self) -> bool:
        return psutil.virtual_memory().percent < self.umbral_ram_pct


class AlforjaSpooler:
    """Cola FIFO en disco. Zero RAM impact."""

    def __init__(self, ruta_spool: str = SPOOL_DIR) -> None:
        self.path = Path(ruta_spool)
        self.path.mkdir(parents=True, exist_ok=True)

    def guardar_tarea(self, tarea: dict) -> None:
        tid = tarea.get("id", "unknown")
        (self.path / f"task_{tid}.json").write_text(json.dumps(tarea, ensure_ascii=False))
        logger.info(f"[ALFORJA] Tarea {tid} desviada a disco")

    def obtener_siguiente_tarea(self) -> dict | None:
        archivos = sorted(self.path.glob("task_*.json"))
        if not archivos:
            return None
        try:
            tarea = json.loads(archivos[0].read_text())
            archivos[0].unlink()
            return tarea
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"[ALFORJA] Error leyendo spool: {e}")
            return None


class CajaRegistradora:
    """Procesamiento con purga de memoria."""

    async def ejecutar(self, tarea: dict) -> None:
        try:
            logger.info(f"[CAJA] Ejecutando: {tarea.get('id')}")
            await asyncio.sleep(0.2)
        finally:
            gc.collect()


class AsignadorCanales:
    """Orquestador con prioridad: spool > cola RAM > sleep."""

    def __init__(self) -> None:
        self.ram = ControladorMemoria()
        self.spool = AlforjaSpooler()
        self.caja = CajaRegistradora()
        self.cola: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._bucle: asyncio.Task | None = None

    async def inyectar_tarea(self, tarea: dict) -> None:
        if self.ram.tiene_luz_verde() and self.cola.empty():
            try:
                self.cola.put_nowait(tarea)
            except asyncio.QueueFull:
                self.spool.guardar_tarea(tarea)
        else:
            self.spool.guardar_tarea(tarea)

    async def bucle_procesamiento(self) -> None:
        while True:
            try:
                if self.ram.tiene_luz_verde():
                    td = self.spool.obtener_siguiente_tarea()
                    if td:
                        await self.caja.ejecutar(td)
                        await asyncio.sleep(0.1)
                        continue
                if not self.cola.empty():
                    tr = await self.cola.get()
                    if self.ram.tiene_luz_verde():
                        await self.caja.ejecutar(tr)
                    else:
                        self.spool.guardar_tarea(tr)
                    self.cola.task_done()
            except Exception as e:
                logger.error(f"Error en bucle: {e}")
            await asyncio.sleep(0.1)

    def arrancar(self) -> None:
        self._bucle = asyncio.create_task(self.bucle_procesamiento())


async def main() -> None:
    a = AsignadorCanales()
    a.arrancar()
    for i in range(1, 15):
        await a.inyectar_tarea({"id": f"TX_{i}", "payload": "datos"})
        await asyncio.sleep(0.02)
    await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
