"""PipelineEngine — orquestador compartido.

NO contiene lógica de negocio.
Solo coordina: config → logger → snapshot → subprocess calls.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.logger import Logger
from scripts.pro.tuneladora.snapshot import SnapshotService


class PipelineEngine:
    """Motor compartido para pipelines de mantenimiento y mejora.

    Uso:
        engine = PipelineEngine()
        engine.run_script("scripts/pro/token_screen.py", args=["--json"])
        engine.run_ruff(["check", "--select", "F821", "."])
        engine.snapshot.save("ultimo_ciclo")
    """

    def __init__(self, config: Configuration | None = None) -> None:
        self.config = config or Configuration()
        self.log = Logger(self.config.log_file)
        self.snapshot = SnapshotService(self.config.nervioso, self.log.info)

    def run_script(
        self,
        script: str,
        args: list[str] | None = None,
        timeout: int | None = None,
        capture: bool = True,
    ) -> subprocess.CompletedProcess:
        """Ejecuta un script Python del proyecto con el venv."""
        cmd = [self.config.venv_python, script]
        if args:
            cmd.extend(args)
        t = timeout or self.config.timeout_script
        self.log.info(f"Ejecutando: {' '.join(cmd[-3:])} (timeout={t}s)")
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=capture,
            timeout=t,
            check=False,
            cwd=str(self.config.ura_root),
        )
        if result.returncode != 0:
            self.log.warn(f"Script exit={result.returncode}: {result.stderr[-200:] if result.stderr else ''}")
        return result

    def run_bash(
        self,
        script: str,
        args: list[str] | None = None,
        timeout: int | None = None,
        capture: bool = True,
    ) -> subprocess.CompletedProcess:
        """Ejecuta un script bash del proyecto."""
        cmd = ["bash", script]
        if args:
            cmd.extend(args)
        t = timeout or self.config.timeout_script
        self.log.info(f"Ejecutando bash: {script}")
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=capture,
            timeout=t,
            check=False,
            cwd=str(self.config.ura_root),
        )

    def run_ruff(
        self,
        args: list[str],
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Ejecuta ruff con argumentos."""
        cmd = [self.config.ruff] + args
        t = timeout or self.config.timeout_ruff
        self.log.info(f"Ruff: {' '.join(args)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=t,
            check=False,
            cwd=str(self.config.ura_root),
        )
        if result.returncode != 0 and result.stderr:
            self.log.warn(f"Ruff stderr: {result.stderr[:200]}")
        return result

    def run_git(self, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Ejecuta git con argumentos."""
        return subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(self.config.ura_root),
        )

    def health_ollama(self) -> list[dict[str, Any]]:
        """Verifica conectividad con Ollama."""
        try:
            import httpx  # noqa: PLC0415

            r = httpx.get(f"{self.config.ollama_url}/api/tags", timeout=5)
            if r.status_code == 200:
                return r.json().get("models", [])
        except Exception:  # noqa: BLE001, S110
            pass
        return []

    def health_disk(self) -> dict[str, Any]:
        """Espacio en disco disponible."""
        try:
            usage = os.statvfs("/")
            return {"libre_gb": round((usage.f_frsize * usage.f_bavail) / 1e9, 1)}
        except Exception:  # noqa: BLE001, S110
            return {"libre_gb": 0}

    def report(self, title: str, data: dict[str, Any]) -> None:
        """Genera informe formateado desde un diccionario."""
        lines = [f"{k}: {v}" for k, v in data.items()]
        self.log.report(title, lines)
