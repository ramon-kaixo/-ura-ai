"""Logger — API única de logging para todo el pipeline."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from pathlib import Path


class Logger:
    """Logger único para el sistema de tuneladoras.

    Escribe a archivo y a stdout simultáneamente.
    """

    def __init__(self, log_file: Path, stream: TextIO | None = None) -> None:
        self._log_file = log_file
        self._stream = stream or sys.stdout
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    def _timestamp(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    def _write(self, level: str, msg: str) -> None:
        ts = self._timestamp()
        line = f"[{ts}] [{level}] {msg}"
        try:
            with Path(self._log_file).open("a") as f:
                f.write(line + "\n")
        except PermissionError:
            pass
        self._stream.write(line + "\n")
        self._stream.flush()

    def info(self, msg: str) -> None:
        self._write("INFO", msg)

    def warn(self, msg: str) -> None:
        self._write("WARN", msg)

    def error(self, msg: str) -> None:
        self._write("ERROR", msg)

    def debug(self, msg: str) -> None:
        self._write("DEBUG", msg)

    def report(self, title: str, lines: list[str]) -> None:
        """Escribe un informe formateado."""
        sep = "═" * 55
        self.info(sep)
        self.info(f"  {title}")
        self.info(sep)
        for line in lines:
            self.info(f"  {line}")
        self.info(sep)
