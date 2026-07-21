"""Interfaz de ejecutor de procesos."""

from __future__ import annotations

from typing import Protocol


class IProcessResult(Protocol):
    """Resultado de una ejecución de proceso."""

    ok: bool
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool
    error: str


class IExecutor(Protocol):
    """Contrato para ejecución de comandos del sistema."""

    def run(self, cmd: list[str], timeout: int = 30, cwd: str | None = None, env: dict[str, str] | None = None) -> IProcessResult: ...
