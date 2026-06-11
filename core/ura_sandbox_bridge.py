#!/usr/bin/env python3
"""URA Sandbox Bridge — Capa de seguridad para todo I/O de internet (Fase 3).

Objetivo: cuando el usuario instale el "ordenador virtual" (VM/contenedor),
todas las descargas, fetches y ejecuciones de OpenClaw pasarán por esa VM.
Hoy no hay VM disponible, así que el bridge funciona en modo `passthrough`.

Modos:
  - "passthrough"  → ejecuta directamente en el host (modo actual)
  - "ssh"          → ejecuta en VM remota vía SSH (cuando esté lista)
  - "lima"         → ejecuta dentro de Lima (https://lima-vm.io) — alternativa Mac sin Docker

Configuración por env vars:
  URA_SANDBOX_MODE        passthrough|ssh|lima
  URA_SANDBOX_SSH_HOST    user@host
  URA_SANDBOX_SSH_KEY     ruta a clave privada
  URA_SANDBOX_LIMA_NAME   nombre de la instancia lima

API estable (no cambia entre modos):

    bridge = get_sandbox()
    text, final_url = await bridge.fetch_page(url)
    output           = await bridge.run_command(["curl", "-s", url])
    payload          = await bridge.run_openclaw(tema)

El día que instales la VM, sólo necesitas exportar URA_SANDBOX_MODE=ssh
(o lima) y el resto del código no cambia.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ura_sandbox_bridge")

ENV_MODE = "URA_SANDBOX_MODE"
ENV_SSH_HOST = "URA_SANDBOX_SSH_HOST"
ENV_SSH_KEY = "URA_SANDBOX_SSH_KEY"
ENV_LIMA_NAME = "URA_SANDBOX_LIMA_NAME"

VALID_MODES = ("passthrough", "ssh", "lima")
DEFAULT_MODE = "passthrough"
DEFAULT_TIMEOUT_S = 60


@dataclass
class SandboxConfig:
    mode: str = DEFAULT_MODE
    ssh_host: str | None = None
    ssh_key: str | None = None
    lima_name: str | None = None
    extra_env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> SandboxConfig:
        mode = os.environ.get(ENV_MODE, DEFAULT_MODE).lower()
        if mode not in VALID_MODES:
            logger.warning("URA_SANDBOX_MODE=%s no válido, usando passthrough", mode)
            mode = DEFAULT_MODE
        return cls(
            mode=mode,
            ssh_host=os.environ.get(ENV_SSH_HOST),
            ssh_key=os.environ.get(ENV_SSH_KEY),
            lima_name=os.environ.get(ENV_LIMA_NAME),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ssh_host": self.ssh_host,
            "ssh_key": self.ssh_key,
            "lima_name": self.lima_name,
        }


class SandboxBridge:
    """Capa de aislamiento de I/O. Hoy passthrough; el día de la VM, swap automático."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig.from_env()

    @property
    def is_isolated(self) -> bool:
        """¿Las operaciones de internet están realmente aisladas del host?"""
        return self.config.mode in ("ssh", "lima")

    # ----------------------------------------------------------- fetch ----

    async def fetch_page(self, url: str, timeout: int = 15_000) -> tuple[str, str | None]:
        """Idéntica firma que `core.stealth_fetcher.fetch_page`."""
        if self.config.mode == "passthrough":
            from core.stealth_fetcher import fetch_page

            return await fetch_page(url, timeout=timeout)

        if self.config.mode == "ssh":
            cmd = [
                "ssh",
                *(["-i", self.config.ssh_key] if self.config.ssh_key else []),
                self.config.ssh_host or "",
                "python",
                "-m",
                "core.stealth_fetcher",
                url,
            ]
            text = await self._run_remote(cmd, timeout_s=int(timeout / 1000) + 10)
            return text or "", url

        if self.config.mode == "lima":
            cmd = [
                "limactl",
                "shell",
                self.config.lima_name or "default",
                "python",
                "-m",
                "core.stealth_fetcher",
                url,
            ]
            text = await self._run_remote(cmd, timeout_s=int(timeout / 1000) + 10)
            return text or "", url

        return "", None

    # --------------------------------------------------------- command ----

    async def run_command(self, args: list[str], *, timeout_s: int = DEFAULT_TIMEOUT_S) -> str:
        """Ejecutar un comando arbitrario dentro del sandbox."""
        if self.config.mode == "passthrough":
            return await self._run_local(args, timeout_s=timeout_s)
        if self.config.mode == "ssh":
            cmd = [
                "ssh",
                *(["-i", self.config.ssh_key] if self.config.ssh_key else []),
                self.config.ssh_host or "",
                shlex.join(args),
            ]
            return await self._run_local(cmd, timeout_s=timeout_s + 5)
        if self.config.mode == "lima":
            cmd = [
                "limactl",
                "shell",
                self.config.lima_name or "default",
                "--",
                *args,
            ]
            return await self._run_local(cmd, timeout_s=timeout_s + 5)
        return ""

    # ----------------------------------------------------- run_openclaw ----

    async def run_openclaw(self, tema: str, *, contexto: str | None = None) -> dict[str, Any]:
        """Invoca OpenClaw siempre dentro del sandbox.

        En modo passthrough delega al `OpenClawClient` nativo.
        En ssh/lima ejecuta el binario remoto y parsea JSON.
        """
        if self.config.mode == "passthrough":
            from core.ura_openclaw_client import get_openclaw_client

            return await get_openclaw_client().search(tema, contexto=contexto)

        # En remoto: ejecutar `openclaw agent --agent main --message "<tema>" --json`
        args = ["openclaw", "agent", "--agent", "main", "--message", tema, "--json"]
        if contexto:
            args += ["--context", contexto]
        try:
            output = await self.run_command(args, timeout_s=180)
        except Exception as e:
            logger.exception("OpenClaw remoto error: %s", e)
            return {
                "tema": tema,
                "nivel": "N3",
                "estado": "error",
                "resultados": [],
                "razonamiento": None,
                "error": f"sandbox_remote: {e}",
            }
        try:
            import json

            raw = json.loads(output) if output.strip() else {}
        except Exception:
            raw = {"text": output}
        # Reusar normalize del cliente local
        from core.ura_openclaw_client import OpenClawAvailability, OpenClawClient

        client = OpenClawClient(availability=OpenClawAvailability(mode="stub"))
        normalized = client._normalize(tema, raw)
        normalized["estado"] = (
            "ok" if normalized["resultados"] or normalized.get("razonamiento") else "error"
        )
        return normalized

    # ------------------------------------------------------------ helpers --

    async def _run_local(self, args: list[str], *, timeout_s: int) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as e:
            logger.warning("comando no encontrado %s: %s", args[0] if args else "", e)
            return ""
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            return ""
        if proc.returncode != 0:
            logger.warning(
                "comando no-cero %s: %s", args[0], stderr_b.decode(errors="ignore")[:200],
            )
            return ""
        return stdout_b.decode(errors="ignore")

    async def _run_remote(self, cmd: list[str], *, timeout_s: int) -> str:
        return await self._run_local(cmd, timeout_s=timeout_s)

    # --------------------------------------------------------- info -------

    def info(self) -> dict[str, Any]:
        return {
            "mode": self.config.mode,
            "is_isolated": self.is_isolated,
            "config": self.config.to_dict(),
        }


# Singleton
_bridge: SandboxBridge | None = None


def get_sandbox() -> SandboxBridge:
    global _bridge
    if _bridge is None:
        _bridge = SandboxBridge()
    return _bridge


def reset_sandbox() -> None:
    """Forzar reinicialización (tras cambiar URA_SANDBOX_MODE)."""
    global _bridge
    _bridge = None
