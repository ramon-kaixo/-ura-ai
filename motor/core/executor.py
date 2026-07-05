"""Executor — abstracción unificada de ejecución de procesos.

Proporciona una interfaz consistente para ejecutar comandos del sistema,
con logging, timeouts y manejo de errores uniforme.

Uso:
    executor = SubprocessExecutor()
    result = executor.run(["ls", "-la"], timeout=10)
    if result.ok:
        print(result.stdout)
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger("ura.executor")


@dataclass
class ProcessResult:
    """Resultado tipado de una ejecución de proceso."""

    ok: bool
    cmd: Sequence[str]
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    timed_out: bool = False
    error: str = ""


class BaseExecutor(ABC):
    """Base abstracta para ejecutores de comandos."""

    @abstractmethod
    def run(
        self,
        cmd: Sequence[str],
        timeout: int = 30,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessResult: ...

    @abstractmethod
    async def arun(
        self,
        cmd: Sequence[str],
        timeout: int = 30,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessResult: ...


class SubprocessExecutor(BaseExecutor):
    """Ejecutor mediante subprocess.run con logging y timeout."""

    def run(
        self,
        cmd: Sequence[str],
        timeout: int = 30,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessResult:
        start = time.monotonic()
        log.debug("Ejecutando: %s (timeout=%ds, cwd=%s)", " ".join(str(c) for c in cmd), timeout, cwd or ".")
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
                check=False,
            )
            elapsed = (time.monotonic() - start) * 1000
            ok = p.returncode == 0
            if not ok:
                log.warning("Comando falló (exit=%d): %s", p.returncode, " ".join(str(c) for c in cmd))
            return ProcessResult(
                ok=ok,
                cmd=cmd,
                returncode=p.returncode,
                stdout=p.stdout,
                stderr=p.stderr,
                duration_ms=elapsed,
                error=p.stderr[:500] if p.stderr else "",
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.monotonic() - start) * 1000
            log.warning("Timeout (%ds) ejecutando: %s", timeout, " ".join(str(c) for c in cmd))
            return ProcessResult(
                ok=False,
                cmd=cmd,
                returncode=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_ms=elapsed,
                timed_out=True,
                error=f"Timeout after {timeout}s",
            )
        except FileNotFoundError:
            elapsed = (time.monotonic() - start) * 1000
            log.error("Comando no encontrado: %s", cmd[0] if cmd else "?")
            return ProcessResult(
                ok=False,
                cmd=cmd,
                returncode=-1,
                stdout="",
                stderr=f"Command not found: {cmd[0] if cmd else '?'}",
                duration_ms=elapsed,
                error=f"Command not found: {cmd[0] if cmd else '?'}",
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            log.exception("Error ejecutando: %s", " ".join(str(c) for c in cmd))
            return ProcessResult(
                ok=False,
                cmd=cmd,
                returncode=-1,
                stdout="",
                stderr=str(e),
                duration_ms=elapsed,
                error=str(e),
            )

    async def arun(
        self,
        cmd: Sequence[str],
        timeout: int = 30,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessResult:
        start = time.monotonic()
        log.debug("(async) Ejecutando: %s (timeout=%ds)", " ".join(str(c) for c in cmd), timeout)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = (time.monotonic() - start) * 1000
                log.warning("(async) Timeout (%ds) ejecutando: %s", timeout, " ".join(str(c) for c in cmd))
                return ProcessResult(
                    ok=False,
                    cmd=cmd,
                    returncode=-1,
                    stdout="",
                    stderr=f"Timeout after {timeout}s",
                    duration_ms=elapsed,
                    timed_out=True,
                    error=f"Timeout after {timeout}s",
                )
            elapsed = (time.monotonic() - start) * 1000
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            ok = proc.returncode == 0
            if not ok:
                log.warning("(async) Comando falló (exit=%d): %s", proc.returncode, " ".join(str(c) for c in cmd))
            return ProcessResult(
                ok=ok,
                cmd=cmd,
                returncode=proc.returncode or -1,
                stdout=stdout,
                stderr=stderr,
                duration_ms=elapsed,
                error=stderr[:500] if stderr else "",
            )
        except FileNotFoundError:
            elapsed = (time.monotonic() - start) * 1000
            return ProcessResult(
                ok=False,
                cmd=cmd,
                returncode=-1,
                stdout="",
                stderr=f"Command not found: {cmd[0] if cmd else '?'}",
                duration_ms=elapsed,
                error=f"Command not found: {cmd[0] if cmd else '?'}",
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            log.exception("(async) Error ejecutando: %s", " ".join(str(c) for c in cmd))
            return ProcessResult(
                ok=False,
                cmd=cmd,
                returncode=-1,
                stdout="",
                stderr=str(e),
                duration_ms=elapsed,
                error=str(e),
            )
