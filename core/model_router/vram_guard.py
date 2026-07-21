"""VRAM Guard — semáforo asíncrono con TTL para control de VRAM."""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)


class ConcurrentVRAMGuard:
    """Semáforo asíncrono con TTL y telemetría para control de VRAM."""

    def __init__(self, max_concurrent_jobs: int = 1, ttl_segundos: float = 30.0) -> None:
        self._max_jobs = max_concurrent_jobs
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._ttl = ttl_segundos
        self._total_enqueue: int = 0
        self._total_timeout: int = 0
        self._total_processed: int = 0

    @property
    def slots_disponibles(self) -> int:
        return self._semaphore._value

    @property
    def esperando_cola(self) -> int:
        waiters = self._semaphore._waiters
        return len(waiters) if waiters is not None else 0

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
        async with self._semaphore:
            espera = time.time() - tiempo_entrada
            if espera > self._ttl:
                self._total_timeout += 1
                log.warning("[VRAM] Petición descartada — TTL expirado (esperó %.1fs > %ds)", espera, self._ttl)
                return {"error": "Timeout en cola de espera", "status_code": 504}
            self._total_processed += 1
            log.debug("[VRAM] Slot adquirido tras %.1fs de espera", espera)
            return await corrutina_inferencia(*args, **kwargs)

    async def adquirir_slot_vram(self, modelo: str, ttl: float | None = None) -> bool:
        """Adquiere slot de VRAM para streaming. Retorna False si TTL expira o se cancela."""
        try:
            ttl_actual = ttl if ttl is not None else self._ttl
            await asyncio.wait_for(self._semaphore.acquire(), timeout=ttl_actual)
            self._total_processed += 1
            log.debug("[VRAM] Slot adquirido para streaming modelo=%s", modelo)
            return True
        except TimeoutError:
            self._total_timeout += 1
            log.warning("[VRAM] Timeout adquiriendo slot para modelo=%s", modelo)
            return False
        except asyncio.CancelledError:
            log.warning("[VRAM] Cancelación durante adquisición de slot para modelo=%s", modelo)
            raise

    async def liberar_slot_vram(self, modelo: str) -> None:
        """Libera slot de VRAM. Se llama SIEMPRE desde finally."""
        self._semaphore.release()
        log.debug("[VRAM] Slot liberado para modelo=%s", modelo)


vram_guard = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=30.0)
