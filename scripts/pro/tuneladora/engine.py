"""PipelineEngine — API v2.3. Orquestador compartido con ledger y checkpoint.

CONTRATO ESTABLE (API v2.3):
  Este módulo define el contrato entre pipelines y plugins.
  No modificar métodos públicos sin versionar el contrato.

Métodos públicos:
  run_script(script, args, timeout)  → CompletedProcess
  run_ruff(args, timeout)            → CompletedProcess
  run_git(args, timeout)             → CompletedProcess
  health_ollama()                    → list[models]
  health_disk()                      → dict[libre_gb]
  report(title, data)                → None

Propiedades públicas:
  config     → Configuration (solo lectura)
  log        → Logger
  snapshot   → SnapshotService
  ledger     → ExecutionLedger
  checkpoint → CheckpointManager
  promotion  → PromotionPolicy

Checkpoint (v2.3):
  checkpoint.is_done(phase) → True si ya se completó
  checkpoint.mark_done(phase) → marca como completada
  checkpoint.resume() → reanuda desde último checkpoint

Change budget (v2.3):
  promotion.set_budget(max_files=50, max_lines=5000)
  promotion.check_budget(files, lines) → True si está dentro del presupuesto

Política de promoción (R1):
  ruff == 0 errores
  pytest == 100% pasados
  benchmarks >= umbral histórico
  auditoría sin bloqueantes
  cambios dentro del presupuesto

Seguridad contra refactorización recursiva (R6):
  PipelineEngine._refactor_ejecutado impide que un mismo ciclo
  lance dos refactorizaciones.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

from scripts.pro.tuneladora.checkpoint import CheckpointManager
from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.ledger import ExecutionLedger
from scripts.pro.tuneladora.logger import Logger
from scripts.pro.tuneladora.snapshot import SnapshotService

CHANGE_BUDGET_DEFAULT = {"max_files": 50, "max_lines": 5000}


class PromotionPolicy:
    """Política de promoción con presupuesto de cambios (R1 + v2.3)."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._results: dict[str, Any] = {}
        self._budget = dict(CHANGE_BUDGET_DEFAULT)

    def set_budget(self, max_files: int = 50, max_lines: int = 5000) -> None:
        self._budget["max_files"] = max_files
        self._budget["max_lines"] = max_lines

    def check_budget(self, files: int, lines: int) -> bool:
        ok = files <= self._budget["max_files"] and lines <= self._budget["max_lines"]
        detail = f"{files}f/{lines}l (límite: {self._budget['max_files']}f/{self._budget['max_lines']}l)"
        self._results["budget"] = {"ok": ok, "detail": detail}
        return ok

    def record(self, check: str, ok: bool, detail: str = "") -> None:
        self._results[check] = {"ok": ok, "detail": detail}

    @property
    def can_promote(self) -> bool:
        if not self._results:
            return False
        return all(r["ok"] for r in self._results.values())

    @property
    def summary(self) -> list[str]:
        lines = []
        for check, r in self._results.items():
            icon = "✅" if r["ok"] else "❌"
            detail = f" — {r['detail']}" if r["detail"] else ""
            lines.append(f"  {icon} {check}{detail}")
        lines.append(f"  {'✅ PROMOCIONABLE' if self.can_promote else '❌ NO PROMOCIONABLE'}")
        return lines


class PipelineEngine:
    """Motor compartido para pipelines — API v2.3.

    Uso:
        engine = PipelineEngine(pipeline="mejora")
        engine.run_script("scripts/pro/token_screen.py", args=["--json"])
        engine.run_ruff(["check", "--select", "F821", "."])
        engine.snapshot.save("ultimo_ciclo")
    """

    _refactor_ejecutado = False  # R6: protección recursiva

    def __init__(self, config: Configuration | None = None, pipeline: str = "") -> None:
        self.config = config or Configuration()
        self.log = Logger(self.config.log_file)
        self.snapshot = SnapshotService(self.config.nervioso, self.log.info)
        self.ledger = ExecutionLedger(self.config.nervioso, pipeline or "unknown")
        self.checkpoint = CheckpointManager(self.config.nervioso, pipeline or "unknown", self.ledger._execution_id)
        self.promotion = PromotionPolicy(self)

    def run_script(
        self,
        script: str,
        args: list[str] | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Ejecuta un script Python del proyecto con el venv."""
        cmd = [self.config.venv_python, script]
        if args:
            cmd.extend(args)
        t = timeout or self.config.timeout_script
        self.log.info(f"Ejecutando: {' '.join(cmd[-3:])} (timeout={t}s)")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=t,
            check=False,
            cwd=str(self.config.ura_root),
        )
        if result.returncode != 0:
            self.log.warn(f"Script exit={result.returncode}: {result.stderr[-200:] if result.stderr else ''}")
        return result

    def run_ruff(
        self,
        args: list[str],
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Ejecuta ruff con argumentos."""
        cmd = [self.config.ruff, *args]
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
            ["git", *args],
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
        except Exception:  # noqa: S110
            pass
        return []

    def health_disk(self) -> dict[str, Any]:
        """Espacio en disco disponible."""
        try:
            usage = os.statvfs("/")
            return {"libre_gb": round((usage.f_frsize * usage.f_bavail) / 1e9, 1)}
        except Exception:
            return {"libre_gb": 0}

    def report(self, title: str, data: dict[str, Any]) -> None:
        """Genera informe formateado desde un diccionario."""
        lines = [f"{k}: {v}" for k, v in data.items()]
        self.log.report(title, lines)
