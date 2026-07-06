"""File lock — exclusión mutua vía flock para el compile.

Usa fcntl.flock con LOCK_EX | LOCK_NB sobre un archivo.
El lock se libera automáticamente si el proceso muere (el SO cierra el fd).
"""

from __future__ import annotations

import fcntl
import logging
import os
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("ura.knowledge.lock")

_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".nervioso"
_DEFAULT_LOCK_FILE = _DEFAULT_CACHE_DIR / "compile.lock"


class LockAcquisitionError(Exception):
    """No se pudo adquirir el lock (otro proceso ya está compilando)."""


@contextmanager
def compile_lock(lock_path: Path = _DEFAULT_LOCK_FILE):
    """Context manager: adquiere flock, libera al salir.

    Raises LockAcquisitionError si otro proceso tiene el lock.
    El lock es liberado automáticamente por el SO si el proceso muere.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd: int | None = None
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        raise LockAcquisitionError(
            f"Compile ya en ejecución (lock: {lock_path})"
        ) from None
    try:
        yield
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(lock_fd)
            except OSError:
                pass
