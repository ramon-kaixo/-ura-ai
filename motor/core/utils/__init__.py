"""motor.core.utils — Utilidades canonicas de la capa motor."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from motor.core.utils.anonymizer import sanitize_text


def atomic_write(
    path: Path | str,
    content: str | bytes,
    mode: str = "w",
    fsync: bool = True,
) -> None:
    """Escribe de forma atomica a un archivo.

    Patron: write-to-temp -> flush -> fsync -> rename -> fsync(dir).
    Garantiza que el archivo destino nunca queda en estado parcial
    ante cortes de energia o crashes.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=str(dest.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, mode) as f:
            f.write(content)
            f.flush()
            if fsync:
                os.fsync(f.fileno())

        Path(tmp_path).replace(dest)

        if fsync:
            dir_fd = os.open(str(dest.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except Exception:
        with contextlib.suppress(OSError):
            Path(tmp_path).unlink()
        raise


def atomic_write_json(path: Path | str, data: Any, fsync: bool = True) -> None:
    """Escribe un objeto JSON de forma atomica."""
    content = json.dumps(data, indent=2, default=str, ensure_ascii=False)
    atomic_write(path, content, mode="w", fsync=fsync)


def file_sha256(path: Path | str) -> str:
    """Calcula SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:  # noqa: PTH123
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_file_integrity(path: Path | str, expected_sha256: str) -> bool:
    """Verifica integridad de archivo via SHA-256."""
    return file_sha256(path) == expected_sha256


__all__ = [
    "atomic_write",
    "atomic_write_json",
    "file_sha256",
    "sanitize_text",
    "verify_file_integrity",
]
