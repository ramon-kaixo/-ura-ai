"""TuneladoraScheduler — ejecucion periodica de pipelines.

Uso:
    scheduler = TuneladoraScheduler()
    scheduler.add_pipeline("health", interval_minutes=5, auto_execute_safe=True)
    scheduler.add_pipeline("cleanup", interval_minutes=60, auto_execute_safe=True)
    scheduler.add_pipeline("full_audit", interval_minutes=360, auto_execute_safe=False)
    scheduler.start()
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine

log = logging.getLogger("ura.tuneladora.scheduler")


@dataclass
class ScheduledPipeline:
    name: str
    interval: timedelta
    auto_execute_safe: bool
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    failure_count: int = 0


class TuneladoraScheduler:
    """Ejecuta pipelines en intervalos configurables."""

    def __init__(self) -> None:
        self._pipelines: list[ScheduledPipeline] = []
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def add_pipeline(self, name: str, interval_minutes: int, auto_execute_safe: bool = True) -> None:
        """Registra un pipeline para ejecucion periodica."""
        interval = timedelta(minutes=interval_minutes)
        pipeline = ScheduledPipeline(
            name=name,
            interval=interval,
            auto_execute_safe=auto_execute_safe,
            next_run=datetime.now(UTC) + timedelta(seconds=5),
        )
        self._pipelines.append(pipeline)
        log.info("Pipeline registrado: %s (cada %d min, auto=%s)", name, interval_minutes, auto_execute_safe)

    def remove_pipeline(self, name: str) -> bool:
        """Elimina un pipeline registrado."""
        before = len(self._pipelines)
        self._pipelines = [p for p in self._pipelines if p.name != name]
        return len(self._pipelines) < before

    def get_status(self) -> list[dict[str, Any]]:
        """Estado actual de todos los pipelines."""
        now = datetime.now(UTC)
        return [
            {
                "name": p.name,
                "interval_minutes": p.interval.total_seconds() / 60,
                "auto_execute_safe": p.auto_execute_safe,
                "last_run": p.last_run.isoformat() if p.last_run else None,
                "next_run": p.next_run.isoformat() if p.next_run else None,
                "overdue": p.next_run is not None and now > p.next_run,
                "run_count": p.run_count,
                "failure_count": p.failure_count,
            }
            for p in self._pipelines
        ]

    async def _run_loop(self) -> None:
        """Loop principal: revisa que pipelines toca ejecutar."""
        log.info("Scheduler iniciado con %d pipelines", len(self._pipelines))
        while self._running:
            now = datetime.now(UTC)
            for pipeline in self._pipelines:
                if pipeline.next_run is None or now >= pipeline.next_run:
                    try:
                        await self._execute_pipeline(pipeline)
                    except Exception as e:
                        log.error("Pipeline %s fallo: %s", pipeline.name, e)
                        pipeline.failure_count += 1
                    pipeline.last_run = now
                    pipeline.next_run = now + pipeline.interval
                    pipeline.run_count += 1
            await asyncio.sleep(5)

    async def _execute_pipeline(self, pipeline: ScheduledPipeline) -> None:
        """Ejecuta un pipeline y registra resultado."""
        engine = PipelineEngine(pipeline=pipeline.name)
        log.info("Ejecutando pipeline programado: %s", pipeline.name)

        if pipeline.name == "health":
            result = engine.health_disk()
            libre_gb = result.get("libre_gb", 0)
            log.info("Health %s: %s GB libres", pipeline.name, libre_gb)
            if libre_gb < 10:
                engine.notify("emergency", "DISCO CRITICO", f"Solo {libre_gb} GB libres")
            elif libre_gb < 50 and pipeline.auto_execute_safe:
                engine.set_dry_run(False)
                engine.run_script("scripts/pro/cleanup_logs.py")

        elif pipeline.name == "cleanup":
            if pipeline.auto_execute_safe:
                engine.set_dry_run(False)
                engine.run_script("scripts/pro/vacuum_sqlite.py")
                engine.run_script("scripts/pro/cleanup_embeddings.py")
                log.info("Cleanup completado: %s", pipeline.name)
            else:
                log.info("Cleanup propuesto para %s (auto_execute_safe=False)", pipeline.name)

        elif pipeline.name == "full_audit":
            # full_audit nunca se auto-ejecuta (auto_execute_safe=False)
            engine.health_disk()
            engine.health_ollama()
            engine.run_ruff(["check", "--output-format", "concise", "."])
            log.info("Full audit completado: %s", pipeline.name)

        else:
            log.warning("Pipeline desconocido: %s", pipeline.name)

        engine.ledger.set_result("completed")
        engine.ledger.save()

    def start(self) -> None:
        """Inicia el scheduler en background."""
        if self._running:
            log.warning("Scheduler ya esta en ejecucion")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info("Scheduler iniciado")

    def stop(self) -> None:
        """Detiene el scheduler."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        log.info("Scheduler detenido")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def pipeline_count(self) -> int:
        return len(self._pipelines)
