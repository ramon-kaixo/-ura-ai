#!/usr/bin/env python3
"""
URA File Lock - Bloqueo de archivos y escritura segura de JSON
"""

import fcntl
import json
import logging
import os
from pathlib import Path
from types import TracebackType

logger = logging.getLogger(__name__)


class FileLock:
    """Context manager para bloqueo exclusivo de archivos usando flock."""

    def __init__(self, lock_path: str | Path, timeout: float = 10.0):
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "FileLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: TracebackType) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


class SafeJSONFile:
    """Lectura/escritura atómica de JSON con bloqueo de archivo."""

    def __init__(self, path: str | Path, default: dict | None = None):
        self.path = Path(path)
        self._lock_path = self.path.with_suffix(".lock")
        self._default = default or {}

    def read(self) -> dict:
        with FileLock(self._lock_path):
            if not self.path.exists():
                return dict(self._default)
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Error leyendo %s: %s", self.path, e)
                return dict(self._default)

    def write(self, data: dict) -> None:
        with FileLock(self._lock_path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    def update(self, updates: dict) -> None:
        current = self.read()
        current.update(updates)
        self.write(current)
