"""Tests para motor.observability.instrumentation (Instrumentation wrappers)."""
from __future__ import annotations

from unittest import mock

import pytest

from motor.observability.instrumentation import Instrumentation, _wrap


class _FakeBus:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_publish = False
        self.fail_emit = False

    def publish(self, topic: str, payload: object, *, source: str = "system") -> None:
        if self.fail_publish:
            raise RuntimeError("boom")
        self.calls.append(f"publish:{topic}:{source}")

    def emit_sync(self, topic: str, payload: object, *, source: str = "system") -> list[object]:
        if self.fail_emit:
            raise RuntimeError("boom")
        self.calls.append(f"emit_sync:{topic}:{source}")
        return ["r1"]


class _FakeRegistry:
    def __init__(self) -> None:
        self._instances: dict[str, object] = {"a": object()}
        self.fail = False

    def _load(self, name: str) -> object | None:
        if self.fail:
            return None
        return self._instances.get(name)


class _FakePipeline:
    name = "p1"

    def __init__(self) -> None:
        self.stages: list[object] = [object(), object()]


class _FakePipelineResult:
    ok = True
    stages = [mock.MagicMock(ok=True), mock.MagicMock(ok=True)]


class _FakeExecutor:
    def __init__(self) -> None:
        self.result = _FakePipelineResult()
        self.calls: list[object] = []

    def execute(self, pipeline: object, context: dict | None = None) -> _FakePipelineResult:
        self.calls.append((pipeline, context))
        return self.result


class _FakeSubprocess:
    def __init__(self) -> None:
        self.result = mock.MagicMock(timed_out=False, ok=True)
        self.calls: list[tuple] = []

    def run(self, cmd: list[str], timeout: int = 30, cwd: str | None = None, env: dict | None = None) -> object:
        self.calls.append((cmd, timeout, cwd, env))
        return self.result


class _FakeHooks:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def register_plugin_hooks(self, plugin_name: str, plugin: object) -> None:
        self.calls.append((plugin_name, plugin))


class TestWrap:
    def test_wrap_replaces_method(self):
        bus = _FakeBus()

        def _wrapper(original):
            def wrapped(topic, payload, *, source="system"):
                return original(topic, payload, source=source)

            return wrapped

        _wrap(bus, "publish", _wrapper)
        bus.publish("t", {})
        assert bus.calls == ["publish:t:system"]


class TestInstrumentationInit:
    def test_snapshot(self):
        inst = Instrumentation()
        snap = inst.snapshot()
        assert "metrics" in snap
        assert "health" in snap
        assert "readiness" in snap


class TestInstrumentEventBus:
    def test_publish_success_records(self):
        inst = Instrumentation()
        bus = _FakeBus()
        inst.instrument_eventbus(bus)
        bus.publish("tema", {"k": 1}, source="test")
        assert bus.calls == ["publish:tema:test"]
        assert inst.metrics.counter("eventbus_published_total", labels={"topic": "tema"}).get() == 1
        assert inst.health.get_status("eventbus") == "healthy"

    def test_publish_failure_records(self):
        inst = Instrumentation()
        bus = _FakeBus()
        bus.fail_publish = True
        inst.instrument_eventbus(bus)
        with pytest.raises(RuntimeError):
            bus.publish("tema", {})
        assert inst.metrics.counter("eventbus_failures_total", labels={"topic": "tema"}).get() == 1

    def test_emit_sync_success(self):
        inst = Instrumentation()
        bus = _FakeBus()
        inst.instrument_eventbus(bus)
        result = bus.emit_sync("tema", {"k": 1})
        assert result == ["r1"]
        assert bus.calls == ["emit_sync:tema:system"]
        assert inst.metrics.counter("eventbus_emitsync_total", labels={"topic": "tema"}).get() == 1

    def test_emit_sync_failure(self):
        inst = Instrumentation()
        bus = _FakeBus()
        bus.fail_emit = True
        inst.instrument_eventbus(bus)
        with pytest.raises(RuntimeError):
            bus.emit_sync("tema", {})
        assert inst.metrics.counter("eventbus_failures_total", labels={"topic": "tema"}).get() == 1


class TestInstrumentRegistry:
    def test_load_success(self):
        inst = Instrumentation()
        registry = _FakeRegistry()
        inst.instrument_registry(registry)
        result = registry._load("a")
        assert result is not None
        assert inst.metrics.counter("plugins_loaded_total").get() == 1
        assert inst.metrics.gauge("plugins_current_loaded").get() == 1
        assert inst.health.get_status("plugins") == "healthy"
        assert "plugins" in inst.readiness._dependencies

    def test_load_failure(self):
        inst = Instrumentation()
        registry = _FakeRegistry()
        registry.fail = True
        inst.instrument_registry(registry)
        registry._load("x")
        assert inst.metrics.counter("plugins_load_failures_total", labels={"plugin": "x"}).get() == 1
        assert inst.metrics.counter("plugins_loaded_total").get() == 0


class TestInstrumentPipeline:
    def test_execute_success(self):
        inst = Instrumentation()
        executor = _FakeExecutor()
        inst.instrument_pipeline(executor)
        result = executor.execute(_FakePipeline(), {"ctx": 1})
        assert len(executor.calls) == 1
        assert result.ok is True
        assert inst.metrics.counter("pipeline_executed_total", labels={"pipeline": "p1"}).get() == 1
        assert inst.metrics.counter("pipeline_stages_total", labels={"pipeline": "p1"}).get() == 2
        assert inst.metrics.counter("pipeline_completed_total").get() == 1
        assert inst.metrics.counter("pipeline_failed_total").get() == 0
        assert inst.health.get_status("pipeline") == "healthy"

    def test_execute_with_rollbacks(self):
        inst = Instrumentation()
        executor = _FakeExecutor()
        executor.result.stages = [
            mock.MagicMock(ok=True),
            mock.MagicMock(ok=False),
            mock.MagicMock(ok=False),
        ]
        inst.instrument_pipeline(executor)
        executor.execute(_FakePipeline())
        assert inst.metrics.counter("pipeline_rollbacks_total", labels={"pipeline": "p1"}).get() == 2
        assert inst.metrics.counter("pipeline_completed_total").get() == 1

    def test_execute_failure(self):
        inst = Instrumentation()
        executor = _FakeExecutor()
        executor.result = mock.MagicMock(ok=False)
        inst.instrument_pipeline(executor)
        executor.execute(_FakePipeline())
        assert inst.metrics.counter("pipeline_failed_total").get() == 1
        assert inst.metrics.counter("pipeline_completed_total").get() == 0


class TestInstrumentHooks:
    def test_register_hooks(self):
        inst = Instrumentation()
        hooks = _FakeHooks()
        inst.instrument_hooks(hooks)
        hooks.register_plugin_hooks("plugin-x", object())
        assert hooks.calls == [("plugin-x", mock.ANY)]
        assert inst.metrics.counter("hooks_registered_total", labels={"plugin": "plugin-x"}).get() == 1
        assert inst.health.get_status("hooks") == "healthy"


class TestInstrumentSubprocess:
    def test_run_success(self):
        inst = Instrumentation()
        executor = _FakeSubprocess()
        inst.instrument_subprocess(executor)
        result = executor.run(["ls", "-la"], timeout=5)
        assert executor.calls == [(["ls", "-la"], 5, None, None)]
        assert result.ok is True
        assert inst.metrics.counter("subprocess_started_total", labels={"cmd": "ls"}).get() == 1
        assert inst.metrics.counter("subprocess_timeouts_total", labels={"cmd": "ls"}).get() == 0
        assert inst.metrics.counter("subprocess_errors_total", labels={"cmd": "ls"}).get() == 0

    def test_run_timeout(self):
        inst = Instrumentation()
        executor = _FakeSubprocess()
        executor.result = mock.MagicMock(timed_out=True, ok=False)
        inst.instrument_subprocess(executor)
        executor.run(["slow"], timeout=1)
        assert inst.metrics.counter("subprocess_timeouts_total", labels={"cmd": "slow"}).get() == 1
        assert inst.metrics.counter("subprocess_errors_total", labels={"cmd": "slow"}).get() == 1

    def test_run_error(self):
        inst = Instrumentation()
        executor = _FakeSubprocess()
        executor.result = mock.MagicMock(timed_out=False, ok=False)
        inst.instrument_subprocess(executor)
        executor.run(["bad"])
        assert inst.metrics.counter("subprocess_errors_total", labels={"cmd": "bad"}).get() == 1
        assert inst.metrics.counter("subprocess_timeouts_total", labels={"cmd": "bad"}).get() == 0

    def test_run_empty_cmd(self):
        inst = Instrumentation()
        executor = _FakeSubprocess()
        inst.instrument_subprocess(executor)
        executor.run([])
        assert inst.metrics.counter("subprocess_started_total", labels={"cmd": "?"}).get() == 1
