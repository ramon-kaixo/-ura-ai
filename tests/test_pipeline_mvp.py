from __future__ import annotations

# ruff: noqa: SLF001  — acceso a _instances/_entries para inyectar plugins de test
from pathlib import Path
from typing import Any

from motor.events.bus import EventBus
from motor.events.topics import (
    PIPELINE_AFTER_STAGE,
    PIPELINE_BEFORE_STAGE,
    PIPELINE_COMPLETED,
    PIPELINE_FAILED,
    PIPELINE_STARTED,
)
from motor.pipeline.definition import PipelineDefinition, StageDefinition, StageResult
from motor.pipeline.executor import PipelineExecutor
from motor.pipeline.loader import PipelineLoader
from motor.plugin.base import PluginBase
from motor.plugin.manifest import PluginManifest
from motor.plugin.registry_v2 import PluginRegistryV2

# ── Test plugin helpers ──────────────────────────────────────────────────────


class _SimplePlugin(PluginBase):
    def __init__(self, name: str = "simple") -> None:
        super().__init__()
        self.manifest = PluginManifest(name=name, version="1.0.0")
        self.executed = False
        self.rollback_called = False

    def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        self.executed = True
        return {"result": "ok"}

    def rollback(self, context: dict[str, Any] | None = None) -> None:
        self.rollback_called = True


class _FailingPlugin(PluginBase):
    def __init__(self, name: str = "failing") -> None:
        super().__init__()
        self.manifest = PluginManifest(name=name, version="1.0.0")
        self.executed = False

    def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        self.executed = True
        raise RuntimeError("stage failed intentionally")


class _CancellingPlugin(PluginBase):
    def __init__(self, name: str = "cancelling") -> None:
        super().__init__()
        self.manifest = PluginManifest(name=name, version="1.0.0")

    def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"cancelled": False}

    def on_before_stage(self, context: dict[str, Any] | None = None) -> None:
        return None  # cancels


class _ContextPlugin(PluginBase):
    def __init__(self, name: str = "context") -> None:
        super().__init__()
        self.manifest = PluginManifest(name=name, version="1.0.0")
        self.seen_stage = ""

    def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        self.seen_stage = (context or {}).get("stage", "")
        return {"output": f"processed_{self.seen_stage}"}


def _discover_and_stage_plugin(registry: PluginRegistryV2, plugin: PluginBase, name: str) -> None:
    import tempfile

    d = Path(tempfile.mkdtemp()) / name
    d.mkdir(parents=True)
    (d / "plugin.yaml").write_text(
        f"name: {name}\nversion: '1.0.0'\napi_version: '1.0.0'\nentry_point: '{type(plugin).__name__}'\n",
    )
    init_code = (
        f"from motor.plugin.base import PluginBase\n"
        f"class {type(plugin).__name__}(PluginBase):\n"
        f"    def execute(self, context):\n"
        f"        return {{}}\n"
    )
    (d / "__init__.py").write_text(init_code)
    registry.discover([str(d)])
    registry._instances[name] = plugin  # inject test instance


# ── Test PipelineDefinition ──────────────────────────────────────────────────


class TestPipelineDefinition:
    def test_create_minimal(self):
        p = PipelineDefinition(name="test", stages=[StageDefinition(name="s1", plugin="p1")])
        assert p.name == "test"
        assert len(p.stages) == 1
        assert p.stages[0].name == "s1"

    def test_stage_defaults(self):
        s = StageDefinition(name="s1", plugin="p1")
        assert s.config == {}
        assert s.timeout == 30
        assert s.optional is False

    def test_stage_result_defaults(self):
        r = StageResult(name="s1", ok=True, plugin="p1")
        assert r.output == {}
        assert r.error == ""
        assert r.duration_ms == 0.0


# ── Test PipelineLoader ──────────────────────────────────────────────────────


class TestPipelineLoader:
    def test_load_yaml(self, tmp_path: Path):
        f = tmp_path / "pipe.yaml"
        f.write_text("name: test-pipe\nstages:\n  - name: stage1\n    plugin: plugin1\n")
        loader = PipelineLoader(PluginRegistryV2())
        p = loader.load(str(f))
        assert p.name == "test-pipe"
        assert len(p.stages) == 1
        assert p.stages[0].name == "stage1"
        assert p.stages[0].plugin == "plugin1"

    def test_load_json(self, tmp_path: Path):
        f = tmp_path / "pipe.json"
        f.write_text('{"name": "json-pipe", "stages": [{"name": "s1", "plugin": "p1"}]}')
        loader = PipelineLoader(PluginRegistryV2())
        p = loader.load(str(f))
        assert p.name == "json-pipe"

    def test_load_stage_config(self, tmp_path: Path):
        f = tmp_path / "pipe.yaml"
        f.write_text(
            "name: cfg-pipe\nstages:\n  - name: s1\n    plugin: p1\n    config:\n      key: value\n      count: 3\n",
        )
        loader = PipelineLoader(PluginRegistryV2())
        p = loader.load(str(f))
        assert p.stages[0].config["key"] == "value"
        assert p.stages[0].config["count"] == 3

    def test_load_stage_optional(self, tmp_path: Path):
        f = tmp_path / "pipe.yaml"
        f.write_text("name: opt-pipe\nstages:\n  - name: s1\n    plugin: p1\n    optional: true\n")
        loader = PipelineLoader(PluginRegistryV2())
        p = loader.load(str(f))
        assert p.stages[0].optional is True

    def test_validate_empty_name(self, tmp_path: Path):
        f = tmp_path / "pipe.yaml"
        f.write_text("stages:\n  - name: s1\n    plugin: p1\n")
        registry = PluginRegistryV2()
        loader = PipelineLoader(registry)
        p = loader.load(str(f))
        errors = loader.validate(p)
        assert "Pipeline name is required" in errors

    def test_validate_no_stages(self):
        p = PipelineDefinition(name="empty")
        loader = PipelineLoader(PluginRegistryV2())
        errors = loader.validate(p)
        assert "At least one stage is required" in errors

    def test_validate_plugin_not_found(self):
        registry = PluginRegistryV2()
        loader = PipelineLoader(registry)
        p = PipelineDefinition(name="test", stages=[StageDefinition(name="s1", plugin="nonexistent")])
        errors = loader.validate(p)
        assert any("not found" in e for e in errors)


# ── Test PipelineExecutor ────────────────────────────────────────────────────


class TestPipelineExecutor:
    def _setup(self) -> tuple[PipelineExecutor, PluginRegistryV2, EventBus]:
        bus = EventBus()
        registry = PluginRegistryV2()
        executor = PipelineExecutor(registry, bus)
        return executor, registry, bus

    def _setup_exec_reg(self) -> tuple[PipelineExecutor, PluginRegistryV2]:
        executor, registry, _ = self._setup()
        return executor, registry

    def test_successful_execution(self):
        executor, registry = self._setup_exec_reg()
        simple = _SimplePlugin("ok_plugin")
        registry._instances["ok_plugin"] = simple
        registry._entries["ok_plugin"] = None  # minimal entry

        p = PipelineDefinition(name="ok", stages=[StageDefinition(name="stage1", plugin="ok_plugin")])
        result = executor.execute(p)
        assert result.ok is True
        assert len(result.stages) == 1
        assert result.stages[0].ok is True
        assert simple.executed is True

    def test_plugin_not_found(self):
        executor, _ = self._setup_exec_reg()
        p = PipelineDefinition(name="missing", stages=[StageDefinition(name="s1", plugin="no_such")])
        result = executor.execute(p)
        assert result.ok is False
        assert "no_such" in result.error

    def test_stage_exception(self):
        executor, registry = self._setup_exec_reg()
        failing = _FailingPlugin("fail_plugin")
        registry._instances["fail_plugin"] = failing
        registry._entries["fail_plugin"] = None

        p = PipelineDefinition(name="fail", stages=[StageDefinition(name="s1", plugin="fail_plugin")])
        result = executor.execute(p)
        assert result.ok is False
        assert failing.executed is True
        assert "failed intentionally" in result.error

    def test_context_propagation(self):
        executor, registry = self._setup_exec_reg()
        cp = _ContextPlugin("ctx_plugin")
        registry._instances["ctx_plugin"] = cp
        registry._entries["ctx_plugin"] = None

        p = PipelineDefinition(name="ctx", stages=[StageDefinition(name="stageA", plugin="ctx_plugin")])
        result = executor.execute(p)
        assert result.ok is True
        assert cp.seen_stage == "stageA"
        # output from stage propagates to context → next stage sees it
        ctx = {"initial": True}
        result2 = executor.execute(p, context=ctx)
        assert result2.ok is True

    def test_rollback_on_failure(self):
        executor, registry = self._setup_exec_reg()
        simple = _SimplePlugin("good_plugin")
        failing = _FailingPlugin("bad_plugin")
        registry._instances["good_plugin"] = simple
        registry._instances["bad_plugin"] = failing
        registry._entries["good_plugin"] = None
        registry._entries["bad_plugin"] = None

        p = PipelineDefinition(
            name="rollback",
            stages=[
                StageDefinition(name="good", plugin="good_plugin"),
                StageDefinition(name="bad", plugin="bad_plugin"),
            ],
        )
        result = executor.execute(p)
        assert result.ok is False
        assert simple.executed is True
        assert failing.executed is True
        assert simple.rollback_called is True

    def test_optional_stage_does_not_fail_pipeline(self):
        executor, registry = self._setup_exec_reg()
        failing = _FailingPlugin("opt_fail")
        registry._instances["opt_fail"] = failing
        registry._entries["opt_fail"] = None

        p = PipelineDefinition(
            name="optional",
            stages=[StageDefinition(name="opt", plugin="opt_fail", optional=True)],
        )
        result = executor.execute(p)
        assert result.ok is True
        assert len(result.stages) == 1
        assert result.stages[0].ok is False

    def test_before_stage_hook_cancels_via_eventbus(self):
        bus = EventBus()
        registry = PluginRegistryV2()
        executor = PipelineExecutor(registry, bus)

        simple = _SimplePlugin("cancelled_plugin")
        registry._instances["cancelled_plugin"] = simple
        registry._entries["cancelled_plugin"] = None

        # Subscribe a hook that cancels the stage
        bus.subscribe(PIPELINE_BEFORE_STAGE, lambda e: None, priority=10)

        p = PipelineDefinition(name="cancel", stages=[StageDefinition(name="s1", plugin="cancelled_plugin")])
        result = executor.execute(p)
        assert result.ok is False
        assert "Cancelled by before_stage hook" in result.error
        # Plugin should NOT have been executed
        assert simple.executed is False


class TestPipelineExecutorEventBusEvents:
    def test_publishes_started_completed(self):
        bus = EventBus()
        registry = PluginRegistryV2()
        executor = PipelineExecutor(registry, bus)
        simple = _SimplePlugin("event_plugin")
        registry._instances["event_plugin"] = simple
        registry._entries["event_plugin"] = None

        received = []
        bus.subscribe(PIPELINE_STARTED, lambda e: received.append(("started", e.payload.name)))
        bus.subscribe(PIPELINE_COMPLETED, lambda e: received.append(("completed", e.payload.name)))

        p = PipelineDefinition(name="events", stages=[StageDefinition(name="s1", plugin="event_plugin")])
        executor.execute(p)
        assert len(received) == 2
        assert received[0] == ("started", "events")
        assert received[1] == ("completed", "events")

    def test_publishes_failed_on_error(self):
        bus = EventBus()
        registry = PluginRegistryV2()
        executor = PipelineExecutor(registry, bus)

        received = []
        bus.subscribe(PIPELINE_FAILED, lambda e: received.append(e.payload.name))

        p = PipelineDefinition(name="fail-events", stages=[StageDefinition(name="s1", plugin="nonexistent")])
        executor.execute(p)
        assert received == ["fail-events"]

    def test_publishes_after_stage(self):
        bus = EventBus()
        registry = PluginRegistryV2()
        executor = PipelineExecutor(registry, bus)
        simple = _SimplePlugin("after_plugin")
        registry._instances["after_plugin"] = simple
        registry._entries["after_plugin"] = None

        received = []
        bus.subscribe(PIPELINE_AFTER_STAGE, lambda e: received.append(e.payload.hook))

        p = PipelineDefinition(name="after", stages=[StageDefinition(name="s1", plugin="after_plugin")])
        executor.execute(p)
        assert received == ["after_stage"]


class TestPipelineBenchmark:
    def test_basic_pipeline_under_100ms(self):
        bus = EventBus()
        registry = PluginRegistryV2()
        executor = PipelineExecutor(registry, bus)

        plugins = [_SimplePlugin(f"plugin_{i}") for i in range(5)]
        stages = []
        for i, p in enumerate(plugins):
            registry._instances[f"plugin_{i}"] = p
            registry._entries[f"plugin_{i}"] = None
            stages.append(StageDefinition(name=f"s{i}", plugin=f"plugin_{i}"))

        import time

        p = PipelineDefinition(name="bench", stages=stages)
        start = time.monotonic()
        result = executor.execute(p)
        elapsed = (time.monotonic() - start) * 1000
        assert result.ok is True
        assert elapsed < 100, f"Pipeline took {elapsed:.1f}ms"
