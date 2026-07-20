"""PipelineEngine — API v1. Orquestador compartido.

CONTRATO ESTABLE (API v1):
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
  config   → Configuration (solo lectura)
  log      → Logger
  snapshot → SnapshotService
  metrics  → MetricsCollector

Política de promoción (R1):
  Para que un cambio se considere promocionable deben cumplirse:
    ruff == 0 errores
    pytest == 100% pasados
    benchmarks >= umbral histórico
    auditoría sin bloqueantes

Seguridad contra refactorización recursiva (R6):
  PipelineEngine._refactor_ejecutado impide que un mismo ciclo
  lance dos refactorizaciones.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.logger import Logger
from scripts.pro.tuneladora.snapshot import SnapshotService


class PromotionPolicy:
    """Política de promoción: decide si un cambio puede promocionarse.

    Criterios (R1):
      ruff == 0 errores
      pytest == 100% passed
      benchmarks >= umbral
      auditoría sin bloqueantes
    """

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._results: dict[str, Any] = {}

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


class MetricsCollector:
    """Métricas históricas por ejecución (R5).

    Almacena duración, plugins, resultados en .nervioso/.
    Permite detectar degradaciones con decenas de ejecuciones.
    """

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._start = time.monotonic()
        self._plugins: dict[str, float] = {}
        self._result: str = "unknown"

    def plugin_done(self, name: str, duration_s: float) -> None:
        self._plugins[name] = duration_s

    def set_result(self, result: str) -> None:
        self._result = result

    def save(self) -> None:
        import json  # noqa: PLC0415

        elapsed = time.monotonic() - self._start
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "duracion_total_s": round(elapsed, 1),
            "resultado": self._result,
            "plugins": self._plugins,
        }
        hist_file = self._engine.config.nervioso / "metrics" / "historial_ejecuciones.jsonl"
        hist_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(hist_file, "a") as f:  # noqa: PTH123
                f.write(json.dumps(entry) + "\n")
        except PermissionError:
            pass


class PipelineEngine:
    """Motor compartido para pipelines — API v1.

    Uso:
        engine = PipelineEngine()
        engine.run_script("scripts/pro/token_screen.py", args=["--json"])
        engine.run_ruff(["check", "--select", "F821", "."])
        engine.snapshot.save("ultimo_ciclo")
    """

    _refactor_ejecutado = False  # R6: protección recursiva

    def __init__(self, config: Configuration | None = None) -> None:
        self.config = config or Configuration()
        self.log = Logger(self.config.log_file)
        self.snapshot = SnapshotService(self.config.nervioso, self.log.info)
        self.metrics = MetricsCollector(self)
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
