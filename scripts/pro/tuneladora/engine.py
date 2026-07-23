"""PipelineEngine — API v2.4. Orquestador compartido con ledger y checkpoint.

v2.4 añade:
  - Métricas Prometheus (registro via MetricsRegistry)
  - Notificaciones vía AlertEngine (motor/brain/)
  - Paralelismo de plugins (threading para tareas independientes)
  - Modo dry_run (simula sin modificar)

Métodos públicos:
  run_script(script, args, timeout, dry_run)  → CompletedProcess
  run_ruff(args, timeout)                      → CompletedProcess
  run_git(args, timeout)                       → CompletedProcess
  health_ollama()                               → list[models]
  health_disk()                                 → dict[libre_gb]
  report(title, data)                           → None
  notify(severity, title, description)          → None
  run_plugins(plugins, parallel)                → dict[str, Any]

Propiedades públicas:
  config     → Configuration (solo lectura)
  log        → Logger
  snapshot   → SnapshotService
  ledger     → ExecutionLedger
  checkpoint → CheckpointManager
  promotion  → PromotionPolicy
  metrics    → TuneladoraMetrics
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any

from scripts.pro.tuneladora.checkpoint import CheckpointManager
from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.ledger import ExecutionLedger
from scripts.pro.tuneladora.logger import Logger
from scripts.pro.tuneladora.snapshot import SnapshotService

CHANGE_BUDGET_DEFAULT = {"max_files": 50, "max_lines": 5000}

# ── Alert Engine (notificaciones, import condicional) ─────────────
try:
    from motor.brain.alerts import Alert, AlertEngine as _AlertEngine
    from motor.brain.observer import BrainObserver

    _HAS_ALERTS = True
except ImportError:
    _HAS_ALERTS = False

# ── Métricas Prometheus ─────────────────────────────────────
try:
    from prometheus_client import Counter as _Counter, Gauge as _Gauge, Histogram as _Histogram, start_http_server

    _exec_total = _Counter("tuneladora_executions_total", "Ejecuciones por plugin y estado", ["plugin", "status"])
    _exec_duration = _Histogram("tuneladora_execution_duration_seconds", "Duracion por plugin", ["plugin"], buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0))
    _plugins_active = _Gauge("tuneladora_plugins_active", "Plugins en ejecucion actual")
    _disk_free = _Gauge("tuneladora_disk_free_gb", "Espacio libre en disco GB")
    _HAS_METRICS = True
except ImportError:
    _HAS_METRICS = False


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
    """Motor compartido para pipelines — API v2.4.

    Uso:
        engine = PipelineEngine(pipeline="mejora")
        engine.run_script("scripts/pro/token_screen.py", args=["--json"])
        engine.run_plugins([("ruff", lambda: engine.run_ruff(["check","."]))])
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
        self._dry_run = False
        self._alert_engine: Any = None
        if _HAS_ALERTS:
            try:
                self._alert_engine = _AlertEngine(BrainObserver())
            except Exception:
                self._alert_engine = None
        # Actualizar gauge de disco al inicio
        if _HAS_METRICS:
            try:
                hd = self.health_disk()
                _disk_free.set(hd.get("libre_gb", 0))
            except Exception:
                pass
        # Iniciar servidor Prometheus si esta habilitado
        if os.environ.get("PROMETHEUS_ENABLED") == "true" and _HAS_METRICS:
            try:
                start_http_server(9091)
                self.log.info("Prometheus metrics server started on :9091")
            except Exception as e:
                self.log.warning(f"Prometheus server fallo: {e}")

    def set_dry_run(self, enabled: bool = True) -> None:
        """Activa/desactiva modo dry_run (simula sin modificar)."""
        self._dry_run = enabled
        self.log.info(f"Dry run: {"ACTIVADO" if enabled else "DESACTIVADO"}")

    # ── Ejecución de scripts ────────────────────────────────────

    def run_script(
        self,
        script: str,
        args: list[str] | None = None,
        timeout: int | None = None,
        dry_run: bool | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Ejecuta un script Python del proyecto con el venv."""
        if dry_run is None:
            dry_run = self._dry_run
        cmd = [self.config.venv_python, script]
        if args:
            cmd.extend(args)
        t = timeout or self.config.timeout_script
        self.log.info(f"Ejecutando: {' '.join(cmd[-3:])} (timeout={t}s, dry_run={dry_run})")

        if dry_run:
            self.log.info(f"[DRY RUN] Simulado: {" ".join(cmd)}")
            self.ledger.add_warning(f"dry_run: {script}")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[dry run]", stderr="")

        t0 = time.monotonic()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=t,
            check=False,
            cwd=str(self.config.ura_root),
        )
        duration = time.monotonic() - t0
        if _HAS_METRICS:
            _exec_total.labels(plugin=script.split("/")[-1].replace(".py", ""), status="success" if result.returncode == 0 else "failure").inc()
            _exec_duration.labels(plugin=script.split("/")[-1].replace(".py", "")).observe(duration)
        if result.returncode != 0:
            self.log.warning("Script exit=%d: %s", result.returncode, (result.stderr or "")[-200:])
            self.notify("warning", f"Script falló: {script}", result.stderr or "")
        return result

    def run_ruff(
        self,
        args: list[str],
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Ejecuta ruff con argumentos."""
        cmd = [self.config.ruff, *args]
        t = timeout or self.config.timeout_ruff
        self.log.info(f"Ruff: {" ".join(args)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=t,
            check=False,
            cwd=str(self.config.ura_root),
        )
        if result.returncode != 0 and result.stderr:
            self.log.warning(f"Ruff stderr: {result.stderr[:200]}")
        return result

    def run_git(self, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        """Ejecuta git con argumentos."""
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(self.config.ura_root),
        )

    # ── Plugins en paralelo ─────────────────────────────────────

    def run_plugins(
        self,
        plugins: list[tuple[str, Any]],
        parallel: bool = True,
    ) -> dict[str, Any]:
        """Ejecuta una lista de plugins (name, callable).

        Si parallel=True, ejecuta en paralelo (threading).
        plugins con dependencias deben ejecutarse secuencialmente
        en una sola llamada.
        """
        results: dict[str, Any] = {}
        if _HAS_METRICS:
            _plugins_active.set(len(plugins))
            for name, fn in plugins:
                _exec_total.labels(plugin=name, status="running").inc()

        if parallel and len(plugins) > 1:
            threads: list[threading.Thread] = []
            thread_results: dict[str, Any] = {}

            def _run(name: str, fn: Any) -> None:
                try:
                    thread_results[name] = fn()
                except Exception as e:
                    thread_results[name] = {"error": str(e)}
                    self.log.warning(f"Plugin {name} falló en thread: {e}")

            for name, fn in plugins:
                t = threading.Thread(target=_run, args=(name, fn), daemon=True)
                threads.append(t)
                t.start()
            for t in threads:
                t.join(timeout=10)
            results = thread_results
        else:
            for name, fn in plugins:
                try:
                    results[name] = fn()
                except Exception as e:
                    results[name] = {"error": str(e)}
                    self.log.warning(f"Plugin {name} falló: {e}")

        if _HAS_METRICS:
            _plugins_active.set(0)
        return results

    # ── Notificaciones vía AlertEngine ──────────────────────────

    def notify(self, severity: str, title: str, description: str = "") -> None:
        """Envía notificación vía AlertEngine si está disponible."""
        if _HAS_ALERTS and self._alert_engine is not None:
            try:
                alert = Alert(
                    severity=severity,
                    title=title,
                    description=description,
                    affected_subsystems=["tuneladora"],
                    timestamp=time.time(),
                )
                self._alert_engine._alert_history.append(alert)
            except Exception as e:
                self.log.debug("Notificacion falló: %s", e)
        else:
            self.log.warning("[NOTIFY] %s: %s — %s", severity.upper(), title, description)

    # ── Health checks ──────────────────────────────────────────

    def health_ollama(self) -> list[dict[str, Any]]:
        """Verifica conectividad con Ollama."""
        try:
            import httpx

            r = httpx.get(f"{self.config.ollama_url}/api/tags", timeout=5)
            if r.status_code == 200:
                return list(r.json().get("models", []))
        except Exception:  # noqa: S110
            pass
        return []

    def health_disk(self) -> dict[str, Any]:
        """Espacio en disco disponible."""
        try:
            usage = os.statvfs("/")
            libre_gb = round((usage.f_frsize * usage.f_bavail) / 1e9, 1)
            if _HAS_METRICS:
                _disk_free.set(libre_gb)
            if libre_gb < 10:
                self.notify("emergency", "DISCO CRITICO", f"Solo {libre_gb}GB libres")
            return {"libre_gb": libre_gb}
        except Exception:
            return {"libre_gb": 0}

    def report(self, title: str, data: dict[str, Any]) -> None:
        """Genera informe formateado desde un diccionario."""
        lines = [f"{k}: {v}" for k, v in data.items()]
        self.log.report(title, lines)
