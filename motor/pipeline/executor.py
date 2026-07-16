from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from motor.events.event import HookEvent, PipelineCompleted, PipelineFailed, PipelineStarted
from motor.events.topics import (
    PIPELINE_AFTER_PIPELINE,
    PIPELINE_AFTER_STAGE,
    PIPELINE_BEFORE_PIPELINE,
    PIPELINE_BEFORE_STAGE,
    PIPELINE_COMPLETED,
    PIPELINE_FAILED,
    PIPELINE_STARTED,
)
from motor.pipeline.definition import PipelineDefinition, PipelineResult, StageDefinition, StageResult

if TYPE_CHECKING:
    from motor.events.bus import EventBus
    from motor.plugin.registry_v2 import PluginRegistryV2

log = logging.getLogger("ura.pipeline.executor")


class PipelineExecutor:
    def __init__(
        self,
        registry: PluginRegistryV2,
        eventbus: EventBus,
    ) -> None:
        self._registry = registry
        self._bus = eventbus

    def execute(
        self,
        pipeline: PipelineDefinition,
        context: dict[str, Any] | None = None,
    ) -> PipelineResult:
        start = time.monotonic()
        context = dict(context or {})
        completed: list[StageResult] = []

        self._bus.publish(
            PIPELINE_STARTED,
            PipelineStarted(name=pipeline.name, config=context),
            source="pipeline_executor",
        )

        self._bus.emit_sync(
            PIPELINE_BEFORE_PIPELINE,
            HookEvent(plugin="", hook="before_pipeline", context=context),
            source="pipeline_executor",
        )

        try:
            for stage in pipeline.stages:
                stage_start = time.monotonic()
                stage_result = self._execute_stage(stage, context)
                stage_result.duration_ms = (time.monotonic() - stage_start) * 1000
                completed.append(stage_result)

                if not stage_result.ok and not stage.optional:
                    self._rollback(pipeline, completed, context)
                    elapsed = (time.monotonic() - start) * 1000
                    result = PipelineResult(
                        ok=False,
                        name=pipeline.name,
                        stages=completed,
                        error=stage_result.error,
                        duration_ms=elapsed,
                    )
                    self._bus.publish(
                        PIPELINE_FAILED,
                        PipelineFailed(name=pipeline.name, error=stage_result.error),
                        source="pipeline_executor",
                    )
                    return result

            self._bus.emit_sync(
                PIPELINE_AFTER_PIPELINE,
                HookEvent(plugin="", hook="after_pipeline", context={"stages": len(completed)}),
                source="pipeline_executor",
            )

            elapsed = (time.monotonic() - start) * 1000
            result = PipelineResult(
                ok=True,
                name=pipeline.name,
                stages=completed,
                duration_ms=elapsed,
            )
            self._bus.publish(
                PIPELINE_COMPLETED,
                PipelineCompleted(name=pipeline.name, result={"stages": len(completed)}),
                source="pipeline_executor",
            )
            return result

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            log.exception("Pipeline %s failed with exception", pipeline.name)
            self._rollback(pipeline, completed, context)
            result = PipelineResult(
                ok=False,
                name=pipeline.name,
                stages=completed,
                error=str(exc),
                duration_ms=elapsed,
            )
            self._bus.publish(
                PIPELINE_FAILED,
                PipelineFailed(name=pipeline.name, error=str(exc)),
                source="pipeline_executor",
            )
            return result

    def _execute_stage(
        self,
        stage: StageDefinition,
        context: dict[str, Any],
    ) -> StageResult:
        responses = self._bus.emit_sync(
            PIPELINE_BEFORE_STAGE,
            HookEvent(plugin=stage.plugin, hook="before_stage", context={"stage": stage.name, "config": stage.config}),
            source="pipeline_executor",
        )
        if any(r is None for r in responses):
            return StageResult(name=stage.name, plugin=stage.plugin, ok=False, error="Cancelled by before_stage hook")

        plugin = self._registry.get(stage.plugin)
        if plugin is None:
            log.warning("Stage '%s': plugin '%s' not found", stage.name, stage.plugin)
            return StageResult(
                name=stage.name,
                plugin=stage.plugin,
                ok=False,
                error=f"Plugin '{stage.plugin}' not found",
            )

        if hasattr(plugin, "on_before_stage"):
            try:
                result = plugin.on_before_stage(
                    {"stage": stage.name, "config": stage.config, "context": context},
                )
                if result is None:
                    return StageResult(
                        name=stage.name,
                        plugin=stage.plugin,
                        ok=False,
                        error="Cancelled by plugin.on_before_stage",
                    )
            except Exception as exc:
                log.warning("Stage '%s': on_before_stage raised: %s", stage.name, exc)
                return StageResult(
                    name=stage.name,
                    plugin=stage.plugin,
                    ok=False,
                    error=f"Plugin on_before_stage error: {exc}",
                )

        try:
            stage_context: dict[str, Any] = {**context, "stage": stage.name, "config": stage.config}
            output = plugin.execute(stage_context)

            if isinstance(output, dict):
                context.update(output)

            self._bus.publish(
                PIPELINE_AFTER_STAGE,
                HookEvent(plugin=stage.plugin, hook="after_stage", context={"result": output}),
                source="pipeline_executor",
            )

            if hasattr(plugin, "on_after_stage"):
                try:
                    plugin.on_after_stage(output)
                except Exception as exc:
                    log.warning("Stage '%s': on_after_stage raised: %s", stage.name, exc)

            output_dict = output if isinstance(output, dict) else {}
            return StageResult(
                name=stage.name,
                plugin=stage.plugin,
                ok=True,
                output=output_dict,
            )

        except Exception as exc:
            log.warning("Stage '%s' failed: %s", stage.name, exc)
            return StageResult(name=stage.name, plugin=stage.plugin, ok=False, error=str(exc))

    def _rollback(
        self,
        pipeline: PipelineDefinition,
        completed: list[StageResult],
        context: dict[str, Any],
    ) -> None:
        for sr in reversed(completed):
            if not sr.ok:
                continue
            try:
                plugin = self._registry.get(sr.plugin)
                if plugin is not None and hasattr(plugin, "rollback"):
                    plugin.rollback(context)
                    log.info("Rollback stage '%s' completed", sr.name)
            except Exception as exc:
                log.warning("Rollback stage '%s' failed: %s", sr.name, exc)
