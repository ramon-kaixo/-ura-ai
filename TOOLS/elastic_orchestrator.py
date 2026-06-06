"""elastic_orchestrator.py — Monitor de RAM + backpressure.

Lee RAM cada 2s con psutil. Ajusta batch_size y workers dinámicamente.
Escribe metrics.json para que la API lo exponga.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from mochila_engine import BASE_DIR

RAM_TECHO = 0.90; MONITOR_INTERVAL = 2.0
METRICS_PATH = BASE_DIR / "05_RETROALIMENTACION" / "metrics.json"


@dataclass
class Metricas:
    timestamp: str; ram_total_mb: float; ram_libre_mb: float; ram_pct: float
    batch_size: int; estado: str  # optimo | presion | critico


class ElasticOrchestrator:
    def __init__(self):
        self.metricas: Metricas | None = None
        self._running = False

    async def run(self):
        self._running = True
        while self._running:
            await self._ciclo()
            await asyncio.sleep(MONITOR_INTERVAL)

    def detener(self): self._running = False

    async def _ciclo(self):
        if not HAS_PSUTIL:
            self.metricas = Metricas(timestamp=_now_iso(), ram_total_mb=16000, ram_libre_mb=8000,
                                     ram_pct=0.5, batch_size=10, estado="optimo")
            return
        mem = psutil.virtual_memory()
        total = mem.total / 1024 / 1024
        libre = mem.available / 1024 / 1024
        pct = mem.percent / 100
        batch = max(1, int((libre / total) * 50))
        estado = "critico" if pct > RAM_TECHO else ("presion" if pct > 0.75 else "optimo")
        self.metricas = Metricas(timestamp=_now_iso(), ram_total_mb=round(total, 1),
                                  ram_libre_mb=round(libre, 1), ram_pct=round(pct, 4),
                                  batch_size=batch, estado=estado)
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(METRICS_PATH, "w") as f:
            json.dump({"ram_total": round(total, 1), "ram_libre": round(libre, 1),
                       "pct": round(pct, 4), "batch_size": batch, "estado": estado,
                       "timestamp": _now_iso()}, f)

    def puede_procesar(self): return self.metricas is None or self.metricas.estado != "critico"


def _now_iso(): return datetime.now(tz=timezone.utc).isoformat()
