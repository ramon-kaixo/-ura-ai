"""Tests de cobertura de motor/pipeline/executor.py (PipelineExecutor)."""

from __future__ import annotations

from typing import Any

from motor.events.bus import EventBus
from motor.pipeline.definition import PipelineDefinition, StageDefinition
from motor.pipeline.executor import PipelineExecutor


class _Plugin:
    def __init__(self, output: Any = None, exc: Exception | None = None) -> None:
        self._out = output
        self._exc = exc
        self.rollback_called = False
        self.rollback_exc: Exception | None = None
        self.raises_rollback = False

    def execute(self, context: dict[str, Any]) -> Any:
        if self._exc is not None:
            raise self._exc
        return self._out

    def rollback(self, context: dict[str, Any]) -> None:
        self.rollback_called = True
        if self.raises_rollback:
            raise RuntimeError("rollback boom")


class _OnBefore:
    def __init__(self, result: Any = "ok", exc: Exception | None = None) -> None:
        self._r = result
        self._e = exc

    def on_before_stage(self, ctx: dict[str, Any]) -> Any:
        if self._e is not None:
            raise self._e
        return self._r

    def execute(self, context: dict[str, Any]) -> Any:
        return {"x": 1}


class _OnAfter:
    def __init__(self, exc: Exception | None = None) -> None:
        self._e = exc

    def on_after_stage(self, output: Any) -> None:
        if self._e is not None:
            raise self._e

    def execute(self, context: dict[str, Any]) -> Any:
        return {"y": 2}


def _registry(plugins: dict[str, Any]):
    class _R:
        def get(self, name: str):
            return plugins.get(name)

    return _R()


def _pipe(stages: list[StageDefinition]) -> PipelineDefinition:
    return PipelineDefinition(
        name="p",
        version="1",
        description="",
        stages=stages,
    )


def _stage(name: str, plugin: str, optional: bool = False) -> StageDefinition:
    return StageDefinition(name=name, plugin=plugin, config={}, timeout=30, optional=optional)


class TestExecute:
    def test_ok(self) -> None:
        bus = EventBus()
        exec_ = PipelineExecutor(_registry({"a": _Plugin({"out": 1})}), bus)
        res = exec_.execute(_pipe([_stage("s1", "a")]), {"ctx": 1})
        assert res.ok
        assert res.name == "p"
        assert len(res.stages) == 1
        assert res.stages[0].output == {"out": 1}
        assert res.stages[0].duration_ms >= 0

    def test_actualiza_contexto_con_salida_dict(self) -> None:
        plugin = _Plugin({"out": 1})
        exec_ = PipelineExecutor(_registry({"a": plugin}), EventBus())
        exec_.execute(_pipe([_stage("s1", "a")]))
        assert plugin.rollback_called is False

    def test_stage_falla_no_optional_rollback_y_anuncia(self) -> None:
        bus = EventBus()
        ok_plugin = _Plugin({"out": 1})
        bad = _Plugin(exc=RuntimeError("boom"))
        seen: list[str] = []
        bus.subscribe("pipeline.failed", lambda e: seen.append(e.payload.name))
        exec_ = PipelineExecutor(_registry({"a": ok_plugin, "b": bad}), bus)
        res = exec_.execute(_pipe([_stage("s1", "a"), _stage("s2", "b")]))
        assert not res.ok
        assert res.error == "boom"
        assert ok_plugin.rollback_called  # rollback del stage OK previo
        assert seen == ["p"]

    def test_stage_falla_optional_continua(self) -> None:
        bus = EventBus()
        bad = _Plugin(exc=RuntimeError("boom"))
        exec_ = PipelineExecutor(_registry({"a": bad}), bus)
        res = exec_.execute(_pipe([_stage("s1", "a", optional=True)]))
        assert res.ok
        assert not res.stages[0].ok

    def test_excepcion_en_anuncio_publicacion(self) -> None:
        bus = EventBus()
        plugin = _Plugin({"ok": 1})

        class _BusExplosivo:
            def publish(self, topic: str, payload, source: str = "") -> None:
                if topic == "pipeline.completed":
                    raise RuntimeError("publish boom")
                self._inner.publish(topic, payload, source=source)

            def emit_sync(self, topic: str, payload, source: str = "") -> list:
                return self._inner.emit_sync(topic, payload, source=source)

            def subscribe(self, *a, **k):
                return self._inner.subscribe(*a, **k)

        inner = EventBus()
        boom = _BusExplosivo()
        boom._inner = inner
        exec_ = PipelineExecutor(_registry({"a": plugin}), boom)
        res = exec_.execute(_pipe([_stage("s1", "a")]))
        assert not res.ok
        assert "publish boom" in res.error


class TestExecuteStage:
    def test_hook_before_stage_cancela(self) -> None:
        bus = EventBus()
        exec_ = PipelineExecutor(_registry({"a": _Plugin({"ok": 1})}), bus)

        class _Cancel:
            def emit_sync(self, topic: str, payload, source: str = "") -> list:
                return [None]

        exec_._bus = _Cancel()
        res = exec_._execute_stage(_stage("s1", "a"), {})
        assert not res.ok
        assert "Cancelled by before_stage hook" in res.error

    def test_plugin_no_encontrado(self) -> None:
        bus = EventBus()
        exec_ = PipelineExecutor(_registry({}), bus)
        res = exec_._execute_stage(_stage("s1", "ghost"), {})
        assert not res.ok
        assert "not found" in res.error

    def test_on_before_stage_cancela(self) -> None:
        bus = EventBus()
        exec_ = PipelineExecutor(_registry({"a": _OnBefore(None)}), bus)
        res = exec_._execute_stage(_stage("s1", "a"), {})
        assert not res.ok
        assert "Cancelled by plugin.on_before_stage" in res.error

    def test_on_before_stage_raise(self) -> None:
        bus = EventBus()
        exec_ = PipelineExecutor(_registry({"a": _OnBefore(exc=ValueError("before boom"))}), bus)
        res = exec_._execute_stage(_stage("s1", "a"), {})
        assert not res.ok
        assert "on_before_stage error" in res.error

    def test_salida_no_dict(self) -> None:
        bus = EventBus()
        exec_ = PipelineExecutor(_registry({"a": _Plugin("string")}), bus)
        res = exec_._execute_stage(_stage("s1", "a"), {})
        assert res.ok
        assert res.output == {}

    def test_on_after_stage_raise_no_falla(self) -> None:
        bus = EventBus()
        exec_ = PipelineExecutor(_registry({"a": _OnAfter(exc=ValueError("after boom"))}), bus)
        res = exec_._execute_stage(_stage("s1", "a"), {})
        assert res.ok

    def test_execute_raise_falla_stage(self) -> None:
        bus = EventBus()
        exec_ = PipelineExecutor(_registry({"a": _Plugin(exc=ValueError("exec boom"))}), bus)
        res = exec_._execute_stage(_stage("s1", "a"), {})
        assert not res.ok
        assert res.error == "exec boom"


class TestRollback:
    def test_rollback_exception_no_propaga(self) -> None:
        bus = EventBus()
        ok_plugin = _Plugin({"out": 1})
        ok_plugin.raises_rollback = True
        bad = _Plugin(exc=RuntimeError("boom"))
        exec_ = PipelineExecutor(_registry({"a": ok_plugin, "b": bad}), bus)
        res = exec_.execute(_pipe([_stage("s1", "a"), _stage("s2", "b")]))
        assert not res.ok  # el rollback fallido no rompe el resultado

    def test_rollback_plugin_sin_rollback(self) -> None:
        bus = EventBus()
        class _SinRollback:
            def execute(self, context: dict[str, Any]) -> Any:
                return {"ok": 1}

        bad = _Plugin(exc=RuntimeError("boom"))
        exec_ = PipelineExecutor(_registry({"a": _SinRollback(), "b": bad}), bus)
        res = exec_.execute(_pipe([_stage("s1", "a"), _stage("s2", "b")]))
        assert not res.ok

