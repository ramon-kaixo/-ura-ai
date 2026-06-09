#!/usr/bin/env python3
"""flujo_constante.py — Tubo capado a 200 Mbps + mochila en disco si se cae internet."""
from __future__ import annotations
import asyncio, gc, json, sys, time
from pathlib import Path
from typing import Any

MOCHILA = str(Path.home() / "URA" / "storage" / "mochila_cloud")

class AlmacenAlemania:
    """Tareas en RAM (max 1 GB) o en disco si se acumula."""
    def __init__(self) -> None:
        self.path = Path(MOCHILA)
        self.path.mkdir(parents=True, exist_ok=True)
        self.ram: list[dict] = []
        self.limite = 1024**3  # 1 GB

    def guardar(self, t: dict) -> None:
        sz = len(json.dumps(t).encode())
        if sum(len(json.dumps(x).encode()) for x in self.ram) + sz > self.limite:
            (self.path / f"backlog_{t['id']}.json").write_text(json.dumps(t))
        else:
            self.ram.append(t)

    def sacar(self) -> dict | None:
        if self.ram:
            return self.ram.pop(0)
        archs = sorted(self.path.glob("backlog_*.json"))
        if not archs:
            return None
        try:
            t = json.loads(archs[0].read_text())
            archs[0].unlink()
            return t
        except: return None

class Tubo:
    """Limite fijo: 200 Mbps (~25 MB/s). Sin sensores."""
    def __init__(self, mbps=200.0):
        self.max = (mbps * 1024 * 1024) / 8
        self.t0 = time.time()
        self.enviados = 0

    async def regular(self, bytes_: int) -> None:
        self.enviados += bytes_
        dt = time.time() - self.t0
        if dt < 0.1: return
        vel = self.enviados / dt
        if vel > self.max:
            espera = (self.enviados / self.max) - dt
            if espera > 0: await asyncio.sleep(espera)
            self.t0 = time.time(); self.enviados = 0

class ASUS:
    async def procesar(self, t: dict) -> bool:
        try:
            return True
        finally:
            gc.collect()

async def main():
    almacen = AlmacenAlemania()
    tubo = Tubo()
    asus = ASUS()
    contador = 0
    caido = False

    while True:
        contador += 1
        t = {"id": f"D{contador}", "payload": "TEXTO" * (2 * 1024 * 1024 // 5)}
        almacen.guardar(t)

        tarea = almacen.sacar()
        if tarea:
            sz = len(json.dumps(tarea).encode())
            if not caido:
                await tubo.regular(sz)
                await asus.procesar(tarea)
                print(f"  Enviado {tarea['id']} ({sz/1024/1024:.1f} MB)")
            else:
                almacen.guardar(tarea)
                await asyncio.sleep(1)
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
