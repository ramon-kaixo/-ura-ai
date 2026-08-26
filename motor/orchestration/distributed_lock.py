"""Distributed Lock — Cerrojo distribuido para auditorias concurrentes.

Usa file locking (fcntl/flock) para coordinar multiples nodos.
 Compatible con Linux (fcntl) y macOS (fcntl con flock fallback).

Flujo:
  1. Intenta adquirir lock en archivo compartido
  2. Si lock adquirido, ejecuta operacion
  3. Si lock fallido, retorna False (otro nodo esta activo)
  4. Lock liberado automaticamente al cerrar el contexto
"""

from __future__ import annotations

import fcntl
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_LOCK_DIR = Path("/tmp/ura-locks")


class DistributedLock:
    """Cerrojo distribuido basado en file locking."""

    def __init__(self, name: str, lock_dir: Path | str = _DEFAULT_LOCK_DIR) -> None:
        self._name = name
        self._lock_dir = Path(lock_dir)
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        self._lock_path = self._lock_dir / f"{name}.lock"
        self._fd: Any | None = None

    def acquire(self, timeout: float = 5.0) -> bool:
        """Intenta adquirir el lock. Timeout en segundos."""
        self._fd = open(self._lock_path, "w")  # noqa: SIM115, PTH123
        start = time.monotonic()

        while True:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fd.write(f"pid={os.getpid()}\nstart={time.time()}\n")
                self._fd.flush()
                log.debug("[LOCK] Acquired: %s (pid=%d)", self._name, os.getpid())
                return True
            except OSError:
                if time.monotonic() - start >= timeout:
                    log.debug("[LOCK] Timeout acquiring: %s", self._name)
                    self._fd.close()
                    self._fd = None
                    return False
                time.sleep(0.1)

    def release(self) -> None:
        """Libera el lock."""
        if self._fd:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                self._fd.close()
            except Exception as e:
                log.debug("[LOCK] Error releasing: %s: %s", self._name, e)
            self._fd = None
            log.debug("[LOCK] Released: %s", self._name)

    def is_locked(self) -> bool:
        """Verifica si el lock esta activo (sin adquirirlo)."""
        try:
            fd = open(self._lock_path)  # noqa: SIM115, PTH123
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Could acquire = NOT locked by someone else
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
                fd.close()
                return False
            except OSError:
                # Could not acquire = locked by someone else
                fd.close()
                return True
        except (OSError, FileNotFoundError):
            return False

    @contextmanager  # type: ignore[type-arg]
    def locked(self, timeout: float = 5.0) -> Any:
        """Context manager que adquiere y libera el lock."""
        acquired = self.acquire(timeout=timeout)
        try:
            yield acquired
        finally:
            self.release()

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *args: object) -> None:
        self.release()


class AuditLock:
    """Lock especifico para auditorias — un solo auditor activo por nodo."""

    def __init__(self, node: str = "default") -> None:
        self._lock = DistributedLock(f"audit-{node}")

    @contextmanager  # type: ignore[type-arg]
    def exclusive(self, timeout: float = 10.0) -> Any:
        """Ejecuta una auditoria exclusiva."""
        with self._lock.locked(timeout=timeout) as acquired:
            if not acquired:
                log.warning("[AUDIT_LOCK] Another auditor is active, skipping")
                yield False
                return
            log.info("[AUDIT_LOCK] Exclusive audit started")
            yield True
            log.info("[AUDIT_LOCK] Exclusive audit completed")
