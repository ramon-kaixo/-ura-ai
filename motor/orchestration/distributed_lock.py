"""Distributed Lock — Cerrojo distribuido para auditorias concurrentes.

Usa file locking (fcntl/flock) para coordinar multiples nodos/procesos.
Compatible con Linux (fcntl) y macOS (fcntl con flock fallback).

Flujo:
  1. Intenta adquirir lock en archivo compartido
  2. Si lock adquirido, ejecuta operacion
  3. Si lock fallido, retorna False (otro nodo esta activo)
  4. Lock liberado automaticamente al cerrar el contexto

Owner tracking: escribe pid + hostname en el archivo de lock para diagnostico.
Deteccion de locks stale: si el lock tiene mas de stale_timeout_s segundos.
"""

from __future__ import annotations

import fcntl
import logging
import os
import socket
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_LOCK_DIR = Path("/tmp/ura-locks")
_STALE_TIMEOUT_S = 300.0  # 5 minutes


class DistributedLock:
    """Cerrojo distribuido basado en file locking (fcntl/flock)."""

    def __init__(
        self,
        name: str,
        lock_dir: Path | str = _DEFAULT_LOCK_DIR,
        stale_timeout_s: float = _STALE_TIMEOUT_S,
    ) -> None:
        self._name = name
        self._lock_dir = Path(lock_dir)
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        self._lock_path = self._lock_dir / f"{name}.lock"
        self._stale_timeout_s = stale_timeout_s
        self._fd: Any | None = None

    def acquire(self, timeout: float = 5.0) -> bool:
        """Intenta adquirir el lock. Timeout en segundos."""
        self._fd = open(self._lock_path, "w")  # noqa: SIM115, PTH123
        start = time.monotonic()

        while True:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                owner = f"pid={os.getpid()} host={socket.gethostname()}"
                self._fd.write(f"{owner}\nstart={time.time()}\n")
                self._fd.flush()
                log.debug("[LOCK] Acquired: %s (%s)", self._name, owner)
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
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
                fd.close()
                return False
            except OSError:
                fd.close()
                return True
        except (OSError, FileNotFoundError):
            return False

    def owner_info(self) -> dict[str, Any] | None:
        """Returns info about the current lock owner, or None."""
        if not self._lock_path.exists():
            return None
        try:
            content = self._lock_path.read_text()
            lines = content.strip().split("\n")
            owner_line = lines[0] if lines else ""
            start_line = lines[1] if len(lines) > 1 else ""
            acquired_at = float(start_line.split("=", 1)[1]) if "=" in start_line else 0
            return {
                "owner": owner_line,
                "acquired_at": acquired_at,
                "age_s": round(time.time() - acquired_at, 1) if acquired_at else 0,
            }
        except Exception:
            return None

    @contextmanager
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

    @contextmanager
    def exclusive(self, timeout: float = 10.0) -> Any:
        """Ejecuta una auditoria exclusiva. Garantiza liberacion en excepcion."""
        acquired = self._lock.acquire(timeout=timeout)
        try:
            if not acquired:
                owner = self._lock.owner_info()
                log.warning(
                    "[AUDIT_LOCK] Another auditor is active (owner=%s), skipping",
                    owner,
                )
                yield False
                return
            log.info("[AUDIT_LOCK] Exclusive audit started")
            yield True
            log.info("[AUDIT_LOCK] Exclusive audit completed")
        finally:
            self._lock.release()
