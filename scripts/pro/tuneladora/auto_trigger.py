"""Fase 1: AutoTrigger — detección automática de mejora continua + integración pipeline."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from scripts.pro.tuneladora.config import Configuration
    from scripts.pro.tuneladora.pipeline.runner import PipelineRunner
    from scripts.pro.tuneladora.pipeline.tools.base import Status
    _PIPELINE_AVAILABLE = True
except ImportError:
    _PIPELINE_AVAILABLE = False

log = logging.getLogger("tuneladora.auto_trigger")


@dataclass(frozen=True)
class TriggerCondition:
    name: str
    description: str
    check_fn: str
    threshold: float | str | None = None
    cooldown: int = 3600


@dataclass
class TriggerEvent:
    condition: str
    value: float | str
    threshold: float | str | None
    timestamp: float = field(default_factory=time.time)
    severity: str = "info"
    message: str = ""


class AutoTrigger:
    def __init__(self, nervioso: Path | None = None, strict: bool = True, mode: str = "gate") -> None:
        self._nervioso = nervioso or Path("/tmp/ura_nervioso")
        self._nervioso.mkdir(parents=True, exist_ok=True)
        self._last_trigger: dict[str, float] = {}
        self._cooldown: dict[str, int] = {}
        self._events: list[TriggerEvent] = []
        self._strict = strict
        self._mode = mode

    @property
    def strict(self) -> bool:
        return self._strict

    @strict.setter
    def strict(self, value: bool) -> None:
        self._strict = value

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        self._mode = value

    # ── Pipeline integration ─────────────────────────────────

    def validate_with_pipeline(self, files: list[Path]) -> dict[str, Any]:
        if not _PIPELINE_AVAILABLE:
            log.warning("Pipeline no disponible, continuando sin validacion")
            return {"status": "skip", "message": "Pipeline no disponible, continuando sin validacion"}
        if not files:
            return {"status": "skip", "message": "No files to validate"}
        try:
            cfg = Configuration()
            runner = PipelineRunner(cfg, mode=self._mode, files=[str(f) for f in files])
            result = runner.run()

            if result == Status.OK:
                return {"status": "ok", "message": "Codigo validado y listo"}
            if result == Status.WARN:
                return {"status": "warn", "message": "Codigo validado con advertencias"}
            return {"status": "fail", "message": "Codigo rechazado, rollback ejecutado. Revisa pending_fixes con --pending"}
        except Exception as exc:
            log.warning("Pipeline fallo, continuando sin validacion: %s", exc)
            return {"status": "skip", "message": f"Pipeline fallo, continuando sin validacion: {exc}"}

    def trigger_validation(self, generated_files: list[Path]) -> dict[str, Any]:
        if not generated_files:
            return {"status": "skip", "message": "No files to validate"}
        result = self.validate_with_pipeline(generated_files)
        s = result["status"]
        msg = result["message"]
        if s == "ok":
            log.info("Pipeline: %s", msg)
        elif s == "warn":
            log.warning("Pipeline: %s", msg)
        elif s == "fail":
            if self._strict:
                log.error("Pipeline: %s", msg)
                return result
            log.warning("Pipeline: %s (non-strict, continuing)", msg)
        else:
            log.warning("Pipeline: %s", msg)
        return result

    def validate_files(self, file_paths: list[Path]) -> dict[str, Any]:
        if not _PIPELINE_AVAILABLE:
            log.warning("Pipeline no disponible, continuando sin validacion")
            return {"status": "skip", "message": "Pipeline no disponible"}
        if not file_paths:
            return {"status": "skip", "message": "No files to validate"}
        try:
            cfg = Configuration()
            runner = PipelineRunner(cfg, mode=self._mode, files=[str(f) for f in file_paths])
            result = runner.run()
            if result == Status.OK:
                return {"status": "ok", "message": "Validacion ok"}
            if result == Status.WARN:
                return {"status": "warn", "message": "Validacion con advertencias"}
            return {"status": "fail", "message": "Validacion fallida"}
        except Exception as exc:
            log.warning("Pipeline fallo: %s", exc)
            return {"status": "skip", "message": f"Pipeline fallo: {exc}"}

    # ── Should-run conditions ────────────────────────────────

    def should_run_maintenance(self) -> bool:
        if self._on_cooldown("maintenance"):
            return False
        return self._check_ruff_errors() or self._check_git_dirty()

    def should_run_refinement(self, file_path: str | Path) -> bool:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        if self._on_cooldown(f"refine:{file_path}"):
            return False
        if not file_path.exists():
            return False
        return self._file_needs_refinement(file_path)

    def should_run_healing(self, pipeline_name: str = "") -> bool:
        key = f"heal:{pipeline_name}" if pipeline_name else "heal:general"
        if self._on_cooldown(key):
            return False
        return self._check_recent_failures(pipeline_name)

    def should_run_intensive(self) -> bool:
        if self._on_cooldown("intensive"):
            return False
        return self._check_time_window(2, 5)

    # ── Cooldown management ──────────────────────────────────

    def set_cooldown(self, key: str, seconds: int) -> None:
        self._last_trigger[key] = time.time()
        self._cooldown[key] = seconds
        log.debug("Cooldown seteado %s: %ds", key, seconds)

    def _on_cooldown(self, key: str) -> bool:
        last = self._last_trigger.get(key)
        if last is None:
            return False
        remaining = self._cooldown.get(key, 3600) - (time.time() - last)
        return remaining > 0

    def cooldown_remaining(self, key: str) -> float:
        last = self._last_trigger.get(key)
        if last is None:
            return 0.0
        cd = self._cooldown.get(key, 3600)
        remaining = cd - (time.time() - last)
        return max(0.0, remaining)

    def reset_cooldown(self, key: str) -> None:
        self._last_trigger.pop(key, None)
        self._cooldown.pop(key, None)

    # ── Event recording ──────────────────────────────────────

    def record_event(self, event: TriggerEvent) -> None:
        self._events.append(event)
        log.log(
            logging.WARNING if event.severity in ("warning", "critical") else logging.INFO,
            "TriggerEvent %s: %s (value=%s, threshold=%s)",
            event.condition, event.message, event.value, event.threshold,
        )

    def get_events(self, limit: int = 50, severity: str | None = None) -> list[TriggerEvent]:
        events = self._events
        if severity:
            events = [e for e in events if e.severity == severity]
        return events[-limit:]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_events": len(self._events),
            "last_trigger": self._last_trigger.copy(),
            "active_cooldowns": {
                k: self.cooldown_remaining(k)
                for k in list(self._cooldown.keys())
            },
        }

    # ── Internal checks ──────────────────────────────────────

    def _check_ruff_errors(self) -> bool:
        try:
            import subprocess

            result = subprocess.run(
                ["ruff", "check", "--output-format", "concise", "--statistics", "."],
                capture_output=True, text=True, timeout=30, check=False,
            )
            count = self._parse_ruff_count(result.stderr or result.stdout)
            if count > 10:
                self.record_event(TriggerEvent(
                    condition="ruff_errors", value=count, threshold=10,
                    severity="warning", message=f"Ruff encontró {count} errores",
                ))
                return True
            return False
        except Exception as e:
            log.debug("Ruff check falló: %s", e)
            return False

    def _parse_ruff_count(self, output: str) -> int:
        import re
        match = re.search(r"Found (\d+) error", output)
        return int(match.group(1)) if match else 0

    def _check_git_dirty(self) -> bool:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            count = len([l for l in result.stdout.split("\n") if l.strip()])
            if count > 5:
                self.record_event(TriggerEvent(
                    condition="git_dirty", value=count, threshold=5,
                    severity="info", message=f"Working tree sucio: {count} archivos",
                ))
                return True
            return count > 0
        except Exception:
            return False

    def _file_needs_refinement(self, file_path: Path) -> bool:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")
            return len(lines) > 300 or sum(1 for l in lines if l.strip()) / max(len(lines), 1) < 0.3
        except Exception:
            return False

    def _check_recent_failures(self, pipeline_name: str = "") -> bool:
        log_file = self._nervioso / "tuneladora_errors.log"
        if not log_file.exists():
            return False
        try:
            content = log_file.read_text()
            error_count = content.count("ERROR") + content.count("CRITICAL")
            return error_count > 3
        except Exception:
            return False

    def _check_time_window(self, min_hour: int, max_hour: int) -> bool:
        now = time.localtime()
        return min_hour <= now.tm_hour <= max_hour
