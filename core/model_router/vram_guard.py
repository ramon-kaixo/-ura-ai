"""VRAM Guard — semáforo con TTL para control de VRAM.

El semáforo es `threading.Semaphore` (no asyncio): el proxy HTTP ejecuta cada
petición con `asyncio.run()` en un thread del socketserver, creando un event
loop efímero por petición. Un `asyncio.Semaphore` global quedaría ligado al
primer loop y lanzaría RuntimeError ("bound to a different event loop") en
peticiones concurrentes posteriores (evidencia: journal model-router,
2026-08-20, repetido cada ~30 min).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time

log = logging.getLogger(__name__)


class ConcurrentVRAMGuard:
    """Semáforo con TTL y telemetría para control de VRAM."""

    def __init__(self, max_concurrent_jobs: int = 1, ttl_segundos: float = 30.0) -> None:
        self._max_jobs = max_concurrent_jobs
        self._semaphore = threading.Semaphore(max_concurrent_jobs)
        self._ttl = ttl_segundos
        self._total_enqueue: int = 0
        self._total_timeout: int = 0
        self._total_processed: int = 0
        self._waiting: int = 0
        self._waiting_lock = threading.Lock()

    @property
    def slots_disponibles(self) -> int:
        return self._semaphore._value

    @property
    def esperando_cola(self) -> int:
        with self._waiting_lock:
            return self._waiting

    def metricas(self) -> dict:
        return {
            "max_concurrent": self._max_jobs,
            "slots_disponibles": self.slots_disponibles,
            "esperando_cola": self.esperando_cola,
            "ttl_segundos": self._ttl,
            "total_enqueue": self._total_enqueue,
            "total_timeout": self._total_timeout,
            "total_processed": self._total_processed,
        }

    async def ejecutar_inferencia_segura(self, corrutina_inferencia, *args, **kwargs):
        tiempo_entrada = time.time()
        self._total_enqueue += 1
        with self._waiting_lock:
            self._waiting += 1
        try:
            if not self._semaphore.acquire(blocking=False):
                adquirido = await asyncio.to_thread(self._semaphore.acquire, True)
            else:
                adquirido = True
        finally:
            with self._waiting_lock:
                self._waiting -= 1
        if not adquirido:
            self._total_timeout += 1
            log.warning("[VRAM] Petición descartada — TTL expirado (esperó %.1fs > %ds)", time.time() - tiempo_entrada, self._ttl)
            return {"error": "Timeout en cola de espera", "status_code": 504}
        try:
            espera = time.time() - tiempo_entrada
            if espera > self._ttl:
                self._total_timeout += 1
                log.warning("[VRAM] Petición descartada — TTL expirado (esperó %.1fs > %ds)", espera, self._ttl)
                return {"error": "Timeout en cola de espera", "status_code": 504}
            self._total_processed += 1
            log.debug("[VRAM] Slot adquirido tras %.1fs de espera", espera)
            return await corrutina_inferencia(*args, **kwargs)
        finally:
            self._semaphore.release()

    async def adquirir_slot_vram(self, modelo: str, ttl: float | None = None) -> bool:
        """Adquiere slot de VRAM para streaming. Retorna False si TTL expira o se cancela."""
        ttl_actual = ttl if ttl is not None else self._ttl
        try:
            with self._waiting_lock:
                self._waiting += 1
            try:
                adquirido = await asyncio.to_thread(self._semaphore.acquire, True, ttl_actual)
            finally:
                with self._waiting_lock:
                    self._waiting -= 1
            if not adquirido:
                self._total_timeout += 1
                log.warning("[VRAM] Timeout adquiriendo slot para modelo=%s", modelo)
                return False
            self._total_processed += 1
            log.debug("[VRAM] Slot adquirido para streaming modelo=%s", modelo)
            return True
        except asyncio.CancelledError:
            log.warning("[VRAM] Cancelación durante adquisición de slot para modelo=%s", modelo)
            raise

    async def liberar_slot_vram(self, modelo: str) -> None:
        """Libera slot de VRAM. Se llama SIEMPRE desde finally."""
        self._semaphore.release()
        log.debug("[VRAM] Slot liberado para modelo=%s", modelo)


vram_guard = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=30.0)
