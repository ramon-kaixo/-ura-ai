#!/usr/bin/env python3
"""flujo_constante.py — Doble via: texto prioritario, crudo en segundo plano."""
from __future__ import annotations
import asyncio, gc, hashlib, json, sys, time
from collections import deque
from pathlib import Path

MOCHILA = str(Path.home() / "URA" / "storage" / "mochila_cloud")
LOG = str(Path.home() / "URA" / "logs" / "flujo.log")
MAX_LOG = 1000

class LogRotatorio:
    """Log rotatorio: guarda las ultimas 1000 lineas, elimina el resto."""
    def __init__(self, path: str = LOG, max_lines: int = MAX_LOG) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max = max_lines
    def escribir(self, msg: str) -> None:
        with self.path.open("a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        lines = self.path.read_text().splitlines()
        if len(lines) > self.max:
            self.path.write_text("\n".join(lines[-self.max:]) + "\n")

log = LogRotatorio()

class AlmacenDobleVia:
    """Dos colas: texto (prioridad) y crudo (segundo plano). Con hash unico."""
    def __init__(self) -> None:
        self.path = Path(MOCHILA)
        self.path.mkdir(parents=True, exist_ok=True)
        self.texto: deque[dict] = deque()
        self.crudo: deque[dict] = deque()
        self.limite_ram = 1024**3  # 1 GB
        self.vistos: set[str] = set()  # hashes para dedup
        self._ram_actual = 0

    def _hash(self, t: dict) -> str:
        return hashlib.sha256(json.dumps(t, sort_keys=True).encode()).hexdigest()[:16]

    def es_duplicado(self, t: dict) -> bool:
        h = self._hash(t)
        if h in self.vistos:
            log.escribir(f"[DEDUP] {t.get('id','?')} duplicado — destruido")
            return True
        self.vistos.add(h)
        # No dejar crecer el historico de hashes infinitamente
        if len(self.vistos) > 100000:
            self.vistos.clear()
        return False

    def guardar(self, t: dict, es_crudo: bool = False) -> None:
        if self.es_duplicado(t):
            return
        cola = self.crudo if es_crudo else self.texto
        sz = len(json.dumps(t).encode())
        if self._ram_actual + sz > self.limite_ram:
            arch = self.path / f"backlog_{t['id']}.json"
            arch.write_text(json.dumps(t))
            log.escribir(f"[DISCO] {t['id']} ({es_crudo=}) desviado a disco")
        else:
            cola.append(t)
            self._ram_actual += sz

    def sacar(self, priorizar_texto: bool = True) -> dict | None:
        # 80% texto, 20% crudo — pero si la cola de texto esta vacia, va crudo
        if priorizar_texto and self.texto:
            t = self.texto.popleft()
            self._ram_actual -= len(json.dumps(t).encode())
            return t
        if self.crudo:
            t = self.crudo.popleft()
            self._ram_actual -= len(json.dumps(t).encode())
            return t
        # Si la RAM esta vacia, buscar en disco
        archs = sorted(self.path.glob("backlog_*.json"))
        if not archs: return None
        try:
            t = json.loads(archs[0].read_text())
            archs[0].unlink()
            return t
        except: return None

class Tubo:
    """Limite fijo: 200 Mbps."""
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
        try: return True
        finally: gc.collect()

async def main():
    almacen = AlmacenDobleVia()
    tubo = Tubo()
    asus = ASUS()
    contador = 0
    caido = False

    while True:
        contador += 1
        # Simular entrada: 80% texto, 20% crudo
        es_crudo = (contador % 5 == 0)
        t = {"id": f"D{contador}", "payload": "TEXTO" * (2 * 1024 * 1024 // 5)}
        almacen.guardar(t, es_crudo=es_crudo)

        tarea = almacen.sacar(priorizar_texto=(contador % 10 != 0))
        if tarea:
            sz = len(json.dumps(tarea).encode())
            if not caido:
                await tubo.regular(sz)
                await asus.procesar(tarea)
                via = "TEXTO" if tarea.get("id","").startswith("D") and int(tarea["id"][1:]) % 5 != 0 else "CRUDO"
                log.escribir(f"[{via}] {tarea['id']} enviado ({sz/1024/1024:.1f} MB)")
            else:
                almacen.guardar(tarea, es_crudo=True)
                await asyncio.sleep(1)
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
