#!/usr/bin/env python3
"""
Thread Pool — FASE 5
──────────────────────
Pool de hilos global para URA. Reemplaza la creación
de QThread aislados. Máximo 10 workers.
"""

import concurrent.futures
import threading
from typing import Callable

from core.logging_config import get_logger

logger = get_logger("thread_pool", log_dir="./logs")


class URAThreadPool:
    """
    Pool de hilos global de URA.

    Uso:
        pool = URAThreadPool()
        future = pool.submit(my_function, arg1, arg2)
        result = future.result(timeout=30)
    """

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        self._active_count = 0

    @property
    def executor(self) -> concurrent.futures.ThreadPoolExecutor:
        if self._executor is None:
            with self._lock:
                if self._executor is None:
                    self._executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=self.max_workers,
                        thread_name_prefix="ura-worker-",
                    )
                    logger.info(f"ThreadPool iniciado: {self.max_workers} workers")
        return self._executor

    def submit(self, fn: Callable, *args, **kwargs) -> concurrent.futures.Future:
        """Envía una tarea al pool."""
        return self.executor.submit(fn, *args, **kwargs)

    def map(self, fn: Callable, *iterables, timeout: float | None = None):
        """Mapea una función sobre iterables en paralelo."""
        return self.executor.map(fn, *iterables, timeout=timeout)

    @property
    def stats(self) -> dict:
        executor = self._executor
        if executor is None:
            return {"workers": 0, "active": 0, "max": self.max_workers}

        # Count active threads
        active = 0
        for thread in threading.enumerate():
            if thread.name.startswith("ura-worker-") and thread.is_alive():
                active += 1

        return {
            "workers": self.max_workers,
            "active": active,
            "total_threads": threading.active_count(),
        }

    def shutdown(self, wait: bool = True):
        """Apaga el pool de forma segura."""
        if self._executor:
            logger.info("ThreadPool apagado")
            self._executor.shutdown(wait=wait, cancel_futures=not wait)
            self._executor = None


# ── Singleton ──────────────────────────────────────────────

_pool: URAThreadPool | None = None


def get_thread_pool() -> URAThreadPool:
    global _pool
    if _pool is None:
        _pool = URAThreadPool(max_workers=10)
    return _pool
