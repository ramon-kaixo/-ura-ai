"""Fase 7: UnifiedScheduler — orquestación central de pipelines + memoria + auto-trigger."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.auto_trigger import AutoTrigger
from scripts.pro.tuneladora.memory.episodic import Episode, EpisodicMemory
from scripts.pro.tuneladora.memory.long_term import LongTermMemory, LTMEntry
from scripts.pro.tuneladora.memory.semantic import SemanticMemory
from scripts.pro.tuneladora.memory.short_term import ShortTermMemory

log = logging.getLogger("tuneladora.unified_scheduler")


@dataclass
class UnifiedPipeline:
    name: str
    handler: Callable[[], dict[str, Any]]
    priority: int = 10
    cooldown: int = 3600
    tags: tuple[str, ...] = ()
    enabled: bool = True
    last_run: float = 0.0
    consecutive_failures: int = 0


class UnifiedScheduler:
    """Coordina pipelines con memoria episódica, auto-trigger y circuit breaker."""

    def __init__(self, nervioso: Path | None = None) -> None:
        self._nervioso = nervioso or Path("/tmp/ura_nervioso")
        self._nervioso.mkdir(parents=True, exist_ok=True)

        self._pipelines: dict[str, UnifiedPipeline] = {}
        self._stm = ShortTermMemory()
        self._ltm = LongTermMemory(self._nervioso / "unified_ltm.db")
        self._episodic = EpisodicMemory(self._nervioso / "unified_episodic.db")
        self._semantic = SemanticMemory(self._nervioso / "unified_semantic.db")
        self._trigger = AutoTrigger(self._nervioso)
        self._max_failures = 5
        self._circuit_tripped: dict[str, float] = {}
        self._circuit_timeout = 300

    # ── Pipeline registration ────────────────────────────────

    def register(self, pipeline: UnifiedPipeline) -> None:
        self._pipelines[pipeline.name] = pipeline
        log.info("Pipeline registrado: %s (prioridad %d)", pipeline.name, pipeline.priority)

    def unregister(self, name: str) -> None:
        self._pipelines.pop(name, None)

    def get_pipeline(self, name: str) -> UnifiedPipeline | None:
        return self._pipelines.get(name)

    def list_pipelines(self) -> list[UnifiedPipeline]:
        return sorted(self._pipelines.values(), key=lambda p: p.priority)

    # ── Execution ────────────────────────────────────────────

    def run_pipeline(self, name: str) -> dict[str, Any]:
        pipeline = self._pipelines.get(name)
        if pipeline is None:
            return {"error": f"Pipeline {name} no encontrado"}

        if not pipeline.enabled:
            return {"status": "skipped", "reason": "disabled"}

        if self._circuit_open(name):
            log.warning("Circuit breaker abierto para %s", name)
            return {"status": "circuit_open", "reason": f"Demasiados fallos ({pipeline.consecutive_failures})"}

        # Cooldown check
        cd = self._trigger.cooldown_remaining(name)
        if cd > 0:
            log.debug("Pipeline %s en cooldown (%.0fs restantes)", name, cd)
            return {"status": "cooldown", "remaining": cd}

        ep_id = f"{name}-{int(time.time())}"
        started = datetime.now(UTC).isoformat()
        t0 = time.time()

        try:
            result = pipeline.handler()
            duration = (time.time() - t0) * 1000
            status = "failed" if result.get("error") else "completed"

            self._episodic.record(Episode(
                episode_id=ep_id, pipeline=name, status=status,
                started=started, finished=datetime.now(UTC).isoformat(),
                summary=result.get("summary", ""), details=result,
                duration_ms=duration, error=result.get("error"),
            ))

            if status == "completed":
                pipeline.consecutive_failures = 0
                self._trigger.set_cooldown(name, pipeline.cooldown)
                self._ltm.store(LTMEntry(
                    key=ep_id, value=result, source=f"pipeline:{name}",
                    tags=pipeline.tags,
                ))
            else:
                pipeline.consecutive_failures += 1
                self._check_circuit_breaker(name, pipeline)

            result["_episode_id"] = ep_id
            result["_duration_ms"] = duration
            result["_status"] = status
            return result

        except Exception as e:
            duration = (time.time() - t0) * 1000
            pipeline.consecutive_failures += 1
            self._episodic.record(Episode(
                episode_id=ep_id, pipeline=name, status="failed",
                started=started, finished=datetime.now(UTC).isoformat(),
                summary=str(e), duration_ms=duration, error=str(e),
            ))
            self._check_circuit_breaker(name, pipeline)
            log.error("Pipeline %s falló: %s", name, e)
            return {"error": str(e), "_episode_id": ep_id, "_status": "failed"}

    # ── Circuit breaker ──────────────────────────────────────

    def _check_circuit_breaker(self, name: str, pipeline: UnifiedPipeline) -> None:
        if pipeline.consecutive_failures >= self._max_failures:
            self._circuit_tripped[name] = time.time()
            log.warning("Circuit breaker activado para %s (%d fallos)", name, pipeline.consecutive_failures)

    def _circuit_open(self, name: str) -> bool:
        tripped = self._circuit_tripped.get(name)
        if tripped is None:
            return False
        if time.time() - tripped > self._circuit_timeout:
            del self._circuit_tripped[name]
            pipeline = self._pipelines.get(name)
            if pipeline:
                pipeline.consecutive_failures = 0
            return False
        return True

    def reset_circuit(self, name: str) -> None:
        self._circuit_tripped.pop(name, None)
        pipeline = self._pipelines.get(name)
        if pipeline:
            pipeline.consecutive_failures = 0

    # ── Run via auto-trigger ─────────────────────────────────

    def run_due(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for pipeline in self.list_pipelines():
            if not pipeline.enabled:
                continue
            name = pipeline.name
            # Respect internal cooldown
            if pipeline.last_run > 0 and time.time() - pipeline.last_run < pipeline.cooldown:
                continue
            # Auto-trigger conditions
            should_run = False
            if name == "maintenance":
                should_run = self._trigger.should_run_maintenance()
            elif name == "healing":
                should_run = self._trigger.should_run_healing()
            elif name == "refinement":
                should_run = self._trigger.should_run_refinement(self._nervioso)
            elif name == "intensive":
                should_run = self._trigger.should_run_intensive()
            else:
                should_run = True

            if should_run:
                result = self.run_pipeline(name)
                pipeline.last_run = time.time()
                results.append(result)
        return results

    # ── Metrics ──────────────────────────────────────────────

    def get_metrics(self) -> dict[str, Any]:
        return {
            "pipelines": len(self._pipelines),
            "enabled": sum(1 for p in self._pipelines.values() if p.enabled),
            "circuit_open": list(self._circuit_tripped.keys()),
            "stm_size": self._stm.size(),
            "ltm_count": self._ltm.count(),
            "episodic_failures_24h": self._episodic.count_failures(since_hours=24),
            "auto_trigger": self._trigger.get_stats(),
        }
