"""Stub: LockManager — gestión de locks para tareas concurrentes."""

import logging
import threading

log = logging.getLogger(__name__)

_locks = {}
_global_lock = threading.Lock()


class LockManager:
    """Gestiona locks nombrados para evitar ejecuciones concurrentes."""

    @staticmethod
    def acquire(name: str, timeout: float = 30) -> bool:
        with _global_lock:
            if name not in _locks:
                _locks[name] = threading.Lock()
        return _locks[name].acquire(timeout=timeout)

    @staticmethod
    def release(name: str) -> None:
        if name in _locks:
            try:
                _locks[name].release()
            except RuntimeError:
                pass


lock_manager = LockManager()
