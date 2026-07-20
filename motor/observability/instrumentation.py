from __future__ import annotations

import logging
import time
from collections.abc import Callable  # noqa: TC003  -- usado en runtime en wrappers
from typing import TYPE_CHECKING, Any

from motor.observability.health import HealthRegistry
from motor.observability.metrics import MetricsRegistry
from motor.observability.readiness import ReadinessRegistry

if TYPE_CHECKING:
    from motor.core.executor import SubprocessExecutor
    from motor.events.bus import EventBus
    from motor.events.hooks import HookManager
    from motor.pipeline.executor import PipelineExecutor
    from motor.plugin.registry_v2 import PluginRegistryV2

log = logging.getLogger("ura.observability.instrumentation")


def _wrap(obj: object, name: str, wrapper: Callable) -> None:
    original = getattr(obj, name)
    setattr(obj, name, wrapper(original))


class Instrumentation:
    def __init__(self) -> None:
        self.metrics = MetricsRegistry()
        self.health = HealthRegistry()
        self.readiness = ReadinessRegistry()

    def instrument_eventbus(self, bus: EventBus) -> EventBus:
        self.health.register_component("eventbus")

        def _wrap_publish(original: Callable) -> Callable:
            def wrapped(topic: str, payload: Any, *, source: str = "system") -> None:  # type: ignore[explicit-any]
                start = time.monotonic()
                try:
                    original(topic, payload, source=source)
                    c = self.metrics.counter("eventbus_published_total", labels={"topic": topic})
                    c.inc()
                except Exception:
                    self.metrics.counter("eventbus_failures_total", labels={"topic": topic}).inc()
                    raise
                finally:
                    self.metrics.timer("eventbus_publish_duration_seconds").record(time.monotonic() - start)

            return wrapped

        def _wrap_emit_sync(original: Callable) -> Callable:
            def wrapped(topic: str, payload: Any, *, source: str = "system") -> list:  # type: ignore[explicit-any]
                start = time.monotonic()
                try:
                    result = original(topic, payload, source=source)
                    self.metrics.counter("eventbus_emitsync_total", labels={"topic": topic}).inc()
                    return result
                except Exception:
                    self.metrics.counter("eventbus_failures_total", labels={"topic": topic}).inc()
                    raise
                finally:
                    self.metrics.timer("eventbus_emitsync_duration_seconds").record(time.monotonic() - start)

            return wrapped

        _wrap(bus, "publish", _wrap_publish)
        _wrap(bus, "emit_sync", _wrap_emit_sync)
        self.health.set_healthy("eventbus")
        return bus

    def instrument_registry(self, registry: PluginRegistryV2) -> PluginRegistryV2:
        self.health.register_component("plugins")

        def _wrap_get(original: Callable) -> Callable:
            def wrapped(name: str) -> Any:  # type: ignore[explicit-any]
                start = time.monotonic()
                result = original(name)
                duration = (time.monotonic() - start) * 1000
                if result is not None:
                    self.metrics.counter("plugins_loaded_total").inc()
                    self.metrics.gauge("plugins_current_loaded").set(len(registry._instances))
                else:
                    self.metrics.counter("plugins_load_failures_total", labels={"plugin": name}).inc()
                self.metrics.timer("plugins_load_duration_ms").record(duration)
                return result

            return wrapped

        _wrap(registry, "_load", _wrap_get)

        self.health.set_healthy("plugins")
        self.readiness.register_dependency("plugins")

        return registry

    def instrument_pipeline(self, executor: PipelineExecutor) -> PipelineExecutor:
        self.health.register_component("pipeline")

        def _wrap_execute(original: Callable) -> Callable:
            def wrapped(pipeline: Any, context: dict[str, Any] | None = None) -> Any:  # type: ignore[explicit-any]
                start = time.monotonic()
                self.metrics.counter("pipeline_executed_total", labels={"pipeline": pipeline.name}).inc()
                c = self.metrics.counter("pipeline_stages_total", labels={"pipeline": pipeline.name})
                c.inc(len(pipeline.stages))

                result = original(pipeline, context)

                elapsed = (time.monotonic() - start) * 1000
                self.metrics.timer("pipeline_duration_ms").record(elapsed)

                if result.ok:
                    self.metrics.counter("pipeline_completed_total").inc()

                    rollback_count = sum(1 for sr in result.stages if not sr.ok)
                    if rollback_count > 0:
                        cnt = self.metrics.counter("pipeline_rollbacks_total", labels={"pipeline": pipeline.name})
                        cnt.inc(rollback_count)
                else:
                    self.metrics.counter("pipeline_failed_total").inc()

                return result

            return wrapped

        _wrap(executor, "execute", _wrap_execute)
        self.health.set_healthy("pipeline")
        return executor

    def instrument_hooks(self, hook_manager: HookManager) -> HookManager:
        self.health.register_component("hooks")

        def _wrap_register(original: Callable) -> Callable:
            def wrapped(plugin_name: str, plugin: Any) -> None:  # type: ignore[explicit-any]
                original(plugin_name, plugin)
                self.metrics.counter("hooks_registered_total", labels={"plugin": plugin_name}).inc()

            return wrapped

        _wrap(hook_manager, "register_plugin_hooks", _wrap_register)
        self.health.set_healthy("hooks")
        return hook_manager

    def instrument_subprocess(self, executor: SubprocessExecutor) -> SubprocessExecutor:
        self.health.register_component("subprocess")

        def _wrap_run(original: Callable) -> Callable:
            def wrapped(cmd: list[str], timeout: int = 30, cwd: str | None = None, env: dict | None = None) -> Any:  # type: ignore[explicit-any]
                cmd_name = cmd[0] if cmd else "?"
                start = time.monotonic()
                self.metrics.counter("subprocess_started_total", labels={"cmd": cmd_name}).inc()
                result = original(cmd, timeout, cwd, env)
                elapsed = (time.monotonic() - start) * 1000
                self.metrics.timer("subprocess_duration_ms").record(elapsed)
                if result.timed_out:
                    self.metrics.counter("subprocess_timeouts_total", labels={"cmd": cmd_name}).inc()
                if not result.ok:
                    self.metrics.counter("subprocess_errors_total", labels={"cmd": cmd_name}).inc()
                return result

            return wrapped

        _wrap(executor, "run", _wrap_run)
        self.health.set_healthy("subprocess")
        return executor

    def snapshot(self) -> dict:
        return {
            "metrics": self.metrics.snapshot(),
            "health": self.health.snapshot(),
            "readiness": self.readiness.snapshot(),
        }
