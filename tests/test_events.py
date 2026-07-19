from __future__ import annotations

import threading
import time

import pytest

from motor.core.state import DegradedMode
from motor.events.bus import EventBus
from motor.events.compat import check_api_compatibility, check_plugin_dependency
from motor.events.event import (
    ConfigChanged,
    Event,
    EventPayload,
    ExecutorCompleted,
    ExecutorStarted,
    HookEvent,
    PipelineCompleted,
    PipelineFailed,
    PipelineStarted,
    PluginError,
    PluginLoaded,
    PluginUnloaded,
    SystemDegraded,
    SystemRestored,
    SystemShutdown,
    SystemStarted,
)
from motor.events.hooks import HOOK_MAX_ERRORS, HookManager
from motor.events.topics import (
    ALL_HOOKS,
    CONFIG_CHANGED,
    EXECUTOR_COMPLETED,
    EXECUTOR_STARTED,
    HOOK_CLI,
    HOOK_PIPELINE,
    HOOK_PREFIX,
    HOOK_SYSTEM,
    PIPELINE_AFTER_PIPELINE,
    PIPELINE_AFTER_STAGE,
    PIPELINE_BEFORE_PIPELINE,
    PIPELINE_BEFORE_STAGE,
    PIPELINE_COMPLETED,
    PIPELINE_FAILED,
    PIPELINE_STARTED,
    PLUGIN_ERROR,
    PLUGIN_LOADED,
    PLUGIN_UNLOADED,
    SYSTEM_DEGRADED,
    SYSTEM_RESTORED,
    SYSTEM_SHUTDOWN,
    SYSTEM_STARTED,
)
from motor.plugin.base import PluginBase
from motor.plugin.manifest import PluginManifest


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def degraded() -> DegradedMode:
    return DegradedMode()


# ═══════════════════════════════════════════════════════════════════════════════
# Event
# ═══════════════════════════════════════════════════════════════════════════════


class TestEventCreation:
    def test_event_requires_topic_and_payload(self) -> None:
        event = Event(topic="test.topic", payload=EventPayload())
        assert event.topic == "test.topic"
        assert isinstance(event.payload, EventPayload)

    def test_event_auto_assigns_timestamp(self) -> None:
        event = Event(topic="t", payload=EventPayload())
        assert event.timestamp != ""
        assert "T" in event.timestamp

    def test_event_auto_assigns_id(self) -> None:
        event = Event(topic="t", payload=EventPayload())
        assert event.id != ""
        assert len(event.id) == 12

    def test_event_preserves_user_id(self) -> None:
        event = Event(topic="t", payload=EventPayload(), id="custom-id")
        assert event.id == "custom-id"

    def test_event_preserves_user_timestamp(self) -> None:
        event = Event(topic="t", payload=EventPayload(), timestamp="2024-01-01T00:00:00")
        assert event.timestamp == "2024-01-01T00:00:00"

    def test_event_preserves_source(self) -> None:
        event = Event(topic="t", payload=EventPayload(), source="test-suite")
        assert event.source == "test-suite"

    def test_event_default_source(self) -> None:
        event = Event(topic="t", payload=EventPayload())
        assert event.source == "system"

    def test_event_is_frozen(self) -> None:
        event = Event(topic="t", payload=EventPayload())
        with pytest.raises(AttributeError):
            event.topic = "other"  # type: ignore[misc]

    def test_event_ids_are_unique(self) -> None:
        ids = {Event(topic="t", payload=EventPayload()).id for _ in range(100)}
        assert len(ids) == 100

    def test_event_repr(self) -> None:
        event = Event(topic="t", payload=EventPayload(), id="abc123")
        r = repr(event)
        assert "Event(" in r
        assert "abc123" in r

    def test_event_with_concrete_payload(self) -> None:
        payload = SystemStarted(python_version="3.11", ura_version="0.29.0")
        event = Event(topic=SYSTEM_STARTED, payload=payload)
        assert event.payload.python_version == "3.11"  # type: ignore[union-attr]
        assert event.payload.ura_version == "0.29.0"  # type: ignore[union-attr]


class TestConcretePayloads:
    def test_system_started(self) -> None:
        p = SystemStarted(python_version="3.12", ura_version="1.0")
        assert p.python_version == "3.12"
        assert p.ura_version == "1.0"

    def test_system_shutdown(self) -> None:
        p = SystemShutdown(reason="upgrade")
        assert p.reason == "upgrade"

    def test_system_degraded(self) -> None:
        p = SystemDegraded(subsystem="qdrant", since="2024-01-01T00:00:00")
        assert p.subsystem == "qdrant"
        assert p.since == "2024-01-01T00:00:00"

    def test_system_restored(self) -> None:
        p = SystemRestored(subsystem="qdrant")
        assert p.subsystem == "qdrant"

    def test_pipeline_started(self) -> None:
        p = PipelineStarted(name="ingest", config={"source": "s3"})
        assert p.name == "ingest"
        assert p.config == {"source": "s3"}

    def test_pipeline_completed(self) -> None:
        p = PipelineCompleted(name="ingest", result={"ok": True})
        assert p.name == "ingest"
        assert p.result == {"ok": True}

    def test_pipeline_failed(self) -> None:
        p = PipelineFailed(name="ingest", error="timeout")
        assert p.name == "ingest"
        assert p.error == "timeout"

    def test_plugin_loaded(self) -> None:
        p = PluginLoaded(name="my-plugin", version="1.2.3")
        assert p.name == "my-plugin"
        assert p.version == "1.2.3"

    def test_plugin_unloaded(self) -> None:
        p = PluginUnloaded(name="my-plugin")
        assert p.name == "my-plugin"

    def test_plugin_error(self) -> None:
        p = PluginError(name="my-plugin", error="kaboom")
        assert p.name == "my-plugin"
        assert p.error == "kaboom"

    def test_hook_event(self) -> None:
        p = HookEvent(plugin="p", hook="pre_ingest", context={"key": "val"})
        assert p.plugin == "p"
        assert p.hook == "pre_ingest"
        assert p.context == {"key": "val"}

    def test_executor_started(self) -> None:
        p = ExecutorStarted(cmd="ruff check")
        assert p.cmd == "ruff check"

    def test_executor_completed(self) -> None:
        p = ExecutorCompleted(cmd="ruff check", returncode=0, duration_ms=150.0)
        assert p.cmd == "ruff check"
        assert p.returncode == 0
        assert p.duration_ms == 150.0

    def test_config_changed(self) -> None:
        p = ConfigChanged(old={"a": 1}, new={"a": 2}, keys=["a"])
        assert p.old == {"a": 1}
        assert p.new == {"a": 2}
        assert p.keys == ["a"]

    def test_payload_defaults(self) -> None:
        assert SystemStarted().python_version == ""
        assert SystemStarted().ura_version == ""
        assert SystemDegraded().subsystem == ""
        assert SystemDegraded().since == ""
        assert PipelineStarted().name == ""
        assert PipelineStarted().config == {}
        assert PipelineFailed().name == ""
        assert ExecutorCompleted().returncode == -1
        assert ExecutorCompleted().duration_ms == 0.0


class TestEventPayloadInheritance:
    def test_all_payloads_are_eventpayload(self) -> None:
        assert isinstance(SystemStarted(), EventPayload)
        assert isinstance(SystemShutdown(), EventPayload)
        assert isinstance(PipelineStarted(), EventPayload)
        assert isinstance(PluginLoaded(), EventPayload)
        assert isinstance(ExecutorCompleted(), EventPayload)
        assert isinstance(ConfigChanged(), EventPayload)


# ═══════════════════════════════════════════════════════════════════════════════
# EventBus — Publish / Subscribe / Unsubscribe
# ═══════════════════════════════════════════════════════════════════════════════


class TestEventBusPublish:
    def test_publish_calls_subscriber(self, bus: EventBus) -> None:
        received: list[Event] = []

        def cb(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.topic", cb)
        bus.publish("test.topic", EventPayload())
        assert len(received) == 1
        assert received[0].topic == "test.topic"

    def test_publish_passes_payload_by_reference(self, bus: EventBus) -> None:
        received: list[EventPayload] = []
        payload = EventPayload()

        def cb(event: Event) -> None:
            received.append(event.payload)

        bus.subscribe("test.topic", cb)
        bus.publish("test.topic", payload)
        assert received[0] is payload

    def test_publish_does_not_call_unsubscribed(self, bus: EventBus) -> None:
        received: list[Event] = []
        sid = bus.subscribe("test.topic", received.append)
        bus.unsubscribe(sid)
        bus.publish("test.topic", EventPayload())
        assert len(received) == 0

    def test_publish_does_not_call_other_topics(self, bus: EventBus) -> None:
        received: list[Event] = []
        bus.subscribe("topic.a", received.append)
        bus.publish("topic.b", EventPayload())
        assert len(received) == 0

    def test_publish_isolates_exceptions(self, bus: EventBus) -> None:
        received: list[Event] = []

        def failing_cb(event: Event) -> None:
            msg = "intentional failure"
            raise RuntimeError(msg)

        def good_cb(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.topic", failing_cb)
        bus.subscribe("test.topic", good_cb)
        bus.publish("test.topic", EventPayload())
        assert len(received) == 1

    def test_publish_multiple_subscribers_same_topic(self, bus: EventBus) -> None:
        results: list[int] = []

        def make_cb(n: int):
            def cb(event: Event) -> None:
                results.append(n)

            return cb

        bus.subscribe("t", make_cb(1))
        bus.subscribe("t", make_cb(2))
        bus.publish("t", EventPayload())
        assert sorted(results) == [1, 2]

    def test_publish_concrete_payload(self, bus: EventBus) -> None:
        received: list[Event] = []

        def cb(event: Event) -> None:
            received.append(event)

        bus.subscribe(SYSTEM_STARTED, cb)
        bus.publish(SYSTEM_STARTED, SystemStarted(python_version="3.12"))
        assert len(received) == 1
        assert received[0].payload.python_version == "3.12"  # type: ignore[union-attr]


class TestEventBusSubscribe:
    def test_subscribe_returns_string_id(self, bus: EventBus) -> None:
        sid = bus.subscribe("t", lambda e: None)
        assert isinstance(sid, str)
        assert len(sid) == 12

    def test_subscribe_unique_ids(self, bus: EventBus) -> None:
        ids = {bus.subscribe("t", lambda e: None) for _ in range(10)}
        assert len(ids) == 10

    def test_subscribe_multiple_same_topic(self, bus: EventBus) -> None:
        bus.subscribe("t", lambda e: None)
        bus.subscribe("t", lambda e: None)
        assert bus.count("t") == 2

    def test_subscribe_pattern_fnmatch(self, bus: EventBus) -> None:
        received: list[Event] = []
        bus.subscribe("pipeline.*", received.append, pattern=True)
        bus.publish("pipeline.started", EventPayload())
        bus.publish("pipeline.failed", EventPayload())
        assert len(received) == 2

    def test_subscribe_pattern_matches_pipeline_topics(self, bus: EventBus) -> None:
        received: list[str] = []

        def cb(event: Event) -> None:
            received.append(event.topic)

        bus.subscribe("pipeline.*", cb, pattern=True)
        bus.publish(PIPELINE_STARTED, EventPayload())
        bus.publish(PIPELINE_COMPLETED, EventPayload())
        bus.publish(PIPELINE_FAILED, EventPayload())
        bus.publish(PIPELINE_BEFORE_PIPELINE, EventPayload())
        bus.publish(PIPELINE_AFTER_PIPELINE, EventPayload())
        bus.publish(PIPELINE_BEFORE_STAGE, EventPayload())
        bus.publish(PIPELINE_AFTER_STAGE, EventPayload())
        assert len(received) == 7

    def test_subscribe_pattern_no_match(self, bus: EventBus) -> None:
        received: list[Event] = []
        bus.subscribe("pipeline.*", received.append, pattern=True)
        bus.publish("system.started", EventPayload())
        assert len(received) == 0

    def test_subscribe_pattern_and_exact_both_match(self, bus: EventBus) -> None:
        results: list[str] = []

        def exact_cb(event: Event) -> None:
            results.append("exact")

        def pattern_cb(event: Event) -> None:
            results.append("pattern")

        bus.subscribe("t", exact_cb)
        bus.subscribe("t.*", pattern_cb, pattern=True)
        bus.publish("t", EventPayload())
        assert "exact" in results
        assert "pattern" not in results  # fnmatch: 't' does not match 't.*'

    def test_empty_topic_subscription(self, bus: EventBus) -> None:
        sid = bus.subscribe("", lambda e: None)
        assert isinstance(sid, str)


class TestEventBusUnsubscribe:
    def test_unsubscribe_removes_exact(self, bus: EventBus) -> None:
        received: list[Event] = []
        sid = bus.subscribe("t", received.append)
        assert bus.unsubscribe(sid) is True
        bus.publish("t", EventPayload())
        assert len(received) == 0

    def test_unsubscribe_removes_pattern(self, bus: EventBus) -> None:
        received: list[Event] = []
        sid = bus.subscribe("p.*", received.append, pattern=True)
        assert bus.unsubscribe(sid) is True
        bus.publish("p.x", EventPayload())
        assert len(received) == 0

    def test_unsubscribe_nonexistent_returns_false(self, bus: EventBus) -> None:
        assert bus.unsubscribe("nonexistent") is False

    def test_unsubscribe_twice_returns_false(self, bus: EventBus) -> None:
        sid = bus.subscribe("t", lambda e: None)
        bus.unsubscribe(sid)
        assert bus.unsubscribe(sid) is False

    def test_unsubscribe_one_keeps_other(self, bus: EventBus) -> None:
        results: list[int] = []
        sid_a = bus.subscribe("t", lambda e: results.append(1))
        bus.subscribe("t", lambda e: results.append(2))
        bus.unsubscribe(sid_a)
        bus.publish("t", EventPayload())
        assert results == [2]

    def test_unsubscribe_does_not_affect_other_topics(self, bus: EventBus) -> None:
        results_a: list[int] = []
        results_b: list[Event] = []
        sid = bus.subscribe("a", lambda e: results_a.append(1))
        bus.subscribe("b", results_b.append)
        bus.unsubscribe(sid)
        bus.publish("b", EventPayload())
        assert len(results_a) == 0
        assert len(results_b) == 1


class TestEventBusPriority:
    def test_higher_priority_called_first(self, bus: EventBus) -> None:
        order: list[int] = []

        bus.subscribe("t", lambda e: order.append(1), priority=10)
        bus.subscribe("t", lambda e: order.append(2), priority=5)
        bus.subscribe("t", lambda e: order.append(3), priority=0)

        bus.publish("t", EventPayload())
        assert order == [1, 2, 3]

    def test_priority_defaults_to_zero(self, bus: EventBus) -> None:
        order: list[int] = []

        bus.subscribe("t", lambda e: order.append(2), priority=0)
        bus.subscribe("t", lambda e: order.append(1))  # default priority 0

        bus.publish("t", EventPayload())
        # Stable sort: first subscribed wins among equal priority
        assert order == [2, 1]

    def test_priority_negative_allowed(self, bus: EventBus) -> None:
        order: list[int] = []

        bus.subscribe("t", lambda e: order.append(1), priority=100)
        bus.subscribe("t", lambda e: order.append(2), priority=-100)

        bus.publish("t", EventPayload())
        assert order == [1, 2]

    def test_priority_affects_pattern_subscribers(self, bus: EventBus) -> None:
        order: list[int] = []

        bus.subscribe("t.*", lambda e: order.append(1), pattern=True, priority=10)
        bus.subscribe("t.*", lambda e: order.append(2), pattern=True, priority=0)

        bus.publish("t.x", EventPayload())
        assert order == [1, 2]


class TestEventBusEmitSync:
    def test_emit_sync_returns_responses(self, bus: EventBus) -> None:
        bus.subscribe("t", lambda e: "response_a")
        bus.subscribe("t", lambda e: "response_b")
        responses = bus.emit_sync("t", EventPayload())
        assert responses == ["response_a", "response_b"]

    def test_emit_sync_exception_returns_none(self, bus: EventBus) -> None:
        def failing(event: Event) -> None:
            error_message = "x"
            raise ValueError(error_message)

        bus.subscribe("t", lambda e: 42)
        bus.subscribe("t", failing)
        responses = bus.emit_sync("t", EventPayload())
        assert responses[0] == 42
        assert responses[1] is None

    def test_emit_sync_empty_topic(self, bus: EventBus) -> None:
        responses = bus.emit_sync("nonexistent", EventPayload())
        assert responses == []

    def test_emit_sync_passes_event(self, bus: EventBus) -> None:
        captured: list[Event] = []

        def cb(event: Event) -> None:
            captured.append(event)
            return event.topic

        bus.subscribe("t", cb)
        responses = bus.emit_sync("t", EventPayload())
        assert responses == ["t"]
        assert len(captured) == 1


class TestEventBusCount:
    def test_count_initial(self, bus: EventBus) -> None:
        assert bus.count() == 0

    def test_count_after_subscribe(self, bus: EventBus) -> None:
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        assert bus.count() == 2

    def test_count_with_topic_filter_exact(self, bus: EventBus) -> None:
        bus.subscribe("a.x", lambda e: None)
        bus.subscribe("a.y", lambda e: None)
        bus.subscribe("b.z", lambda e: None)
        assert bus.count("a.x") == 1

    def test_count_pattern_matches(self, bus: EventBus) -> None:
        bus.subscribe("a.*", lambda e: None, pattern=True)
        bus.subscribe("b.*", lambda e: None, pattern=True)
        # count(topic) matches both exact and pattern subscribers for that topic
        assert bus.count("a.x") == 1
        assert bus.count("a.y") == 1
        assert bus.count("b.x") == 1

    def test_count_exact_and_pattern_topic_filter(self, bus: EventBus) -> None:
        bus.subscribe("t", lambda e: None)
        bus.subscribe("t.*", lambda e: None, pattern=True)
        assert bus.count("t") == 1  # exact matches "t", pattern 't.*' does not match 't'
        assert bus.count("t.x") == 1  # exact 0 + pattern 1 for 't.x'

    def test_count_after_unsubscribe(self, bus: EventBus) -> None:
        sid = bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        bus.unsubscribe(sid)
        assert bus.count() == 1

    def test_count_after_reset(self, bus: EventBus) -> None:
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b.*", lambda e: None, pattern=True)
        bus.reset()
        assert bus.count() == 0


class TestEventBusReset:
    def test_reset_clears_exact(self, bus: EventBus) -> None:
        bus.subscribe("a", lambda e: None)
        bus.reset()
        assert bus.count() == 0

    def test_reset_clears_patterns(self, bus: EventBus) -> None:
        bus.subscribe("a.*", lambda e: None, pattern=True)
        bus.reset()
        assert bus.count() == 0

    def test_reset_publish_does_not_raise(self, bus: EventBus) -> None:
        bus.subscribe("a", lambda e: None)
        bus.reset()
        bus.publish("a", EventPayload())  # should not raise

    def test_reset_allows_resubscribe(self, bus: EventBus) -> None:
        bus.subscribe("a", lambda e: None)
        bus.reset()
        sid = bus.subscribe("a", lambda e: None)
        assert bus.count("a") == 1
        assert isinstance(sid, str)


# ═══════════════════════════════════════════════════════════════════════════════
# EventBus — Async
# ═══════════════════════════════════════════════════════════════════════════════


class TestEventBusPublishAsync:
    def test_publish_async_does_not_block(self, bus: EventBus) -> None:
        received: list[Event] = []

        def slow_cb(event: Event) -> None:
            time.sleep(0.2)
            received.append(event)

        bus.subscribe("slow", slow_cb)
        start = time.monotonic()
        bus.publish_async("slow", EventPayload())
        elapsed = time.monotonic() - start
        assert elapsed < 0.1
        time.sleep(0.3)
        assert len(received) == 1

    def test_publish_async_invokes_eventually(self, bus: EventBus) -> None:
        received: list[Event] = []
        bus.subscribe("t", received.append)
        bus.publish_async("t", EventPayload())
        time.sleep(0.1)
        assert len(received) == 1

    def test_publish_async_multiple_topics(self, bus: EventBus) -> None:
        results: list[str] = []

        def cb_a(event: Event) -> None:
            time.sleep(0.1)
            results.append("a")

        def cb_b(event: Event) -> None:
            results.append("b")

        bus.subscribe("a", cb_a)
        bus.subscribe("b", cb_b)
        bus.publish_async("a", EventPayload())
        bus.publish_async("b", EventPayload())
        time.sleep(0.25)
        assert len(results) == 2

    def test_publish_async_exception_isolation(self, bus: EventBus) -> None:
        results: list[str] = []

        def failing(event: Event) -> None:
            msg = "async fail"
            raise RuntimeError(msg)

        def good(event: Event) -> None:
            results.append("ok")

        bus.subscribe("t", failing)
        bus.subscribe("t", good)
        bus.publish_async("t", EventPayload())
        time.sleep(0.1)
        assert results == ["ok"]


# ═══════════════════════════════════════════════════════════════════════════════
# EventBus — Thread Safety
# ═══════════════════════════════════════════════════════════════════════════════


class TestEventBusThreadSafety:
    def test_concurrent_subscribe_and_publish(self, bus: EventBus) -> None:
        errors: list[Exception] = []
        lock = threading.Lock()
        n = 50

        def subscriber(i: int) -> None:
            try:
                bus.subscribe(f"t.{i}", lambda e: None)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=subscriber, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(errors) == 0
        assert bus.count() == n

    def test_concurrent_publish_and_unsubscribe(self, bus: EventBus) -> None:
        errors: list[Exception] = []
        lock = threading.Lock()
        sids: list[str] = []

        for i in range(20):
            sid = bus.subscribe(f"t.{i}", lambda e: None)
            sids.append(sid)

        def publisher() -> None:
            try:
                for _ in range(50):
                    bus.publish("t.0", EventPayload())
            except Exception as exc:
                with lock:
                    errors.append(exc)

        def unsubscriber() -> None:
            try:
                for sid in sids:
                    bus.unsubscribe(sid)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=publisher),
            threading.Thread(target=unsubscriber),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(errors) == 0

    def test_concurrent_emit_sync(self, bus: EventBus) -> None:
        errors: list[Exception] = []
        lock = threading.Lock()
        bus.subscribe("t", lambda e: e.topic)

        def emitter() -> None:
            try:
                for _ in range(100):
                    bus.emit_sync("t", EventPayload())
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=emitter) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(errors) == 0

    def test_concurrent_reset_and_subscribe(self, bus: EventBus) -> None:
        errors: list[Exception] = []
        lock = threading.Lock()

        def reseter() -> None:
            try:
                for _ in range(10):
                    bus.reset()
            except Exception as exc:
                with lock:
                    errors.append(exc)

        def subscriber() -> None:
            try:
                for _ in range(10):
                    bus.subscribe("t", lambda e: None)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=reseter),
            threading.Thread(target=subscriber),
            threading.Thread(target=reseter),
            threading.Thread(target=subscriber),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Topics
# ═══════════════════════════════════════════════════════════════════════════════


class TestTopicsConstants:
    def test_system_topics(self) -> None:
        assert SYSTEM_STARTED == "system.started"
        assert SYSTEM_SHUTDOWN == "system.shutdown"
        assert SYSTEM_DEGRADED == "system.degraded"
        assert SYSTEM_RESTORED == "system.restored"

    def test_pipeline_topics(self) -> None:
        assert PIPELINE_STARTED == "pipeline.started"
        assert PIPELINE_COMPLETED == "pipeline.completed"
        assert PIPELINE_FAILED == "pipeline.failed"
        assert PIPELINE_BEFORE_PIPELINE == "pipeline.before_pipeline"
        assert PIPELINE_AFTER_PIPELINE == "pipeline.after_pipeline"
        assert PIPELINE_BEFORE_STAGE == "pipeline.before_stage"
        assert PIPELINE_AFTER_STAGE == "pipeline.after_stage"

    def test_plugin_topics(self) -> None:
        assert PLUGIN_LOADED == "plugin.loaded"
        assert PLUGIN_UNLOADED == "plugin.unloaded"
        assert PLUGIN_ERROR == "plugin.error"

    def test_executor_topics(self) -> None:
        assert EXECUTOR_STARTED == "executor.started"
        assert EXECUTOR_COMPLETED == "executor.completed"

    def test_config_topic(self) -> None:
        assert CONFIG_CHANGED == "config.changed"

    def test_hook_prefix(self) -> None:
        assert HOOK_PREFIX == "plugin.hook."

    def test_hook_topic_format(self) -> None:
        for hook in ALL_HOOKS:
            topic = f"{HOOK_PREFIX}{hook}"
            assert topic.startswith("plugin.hook.")
            assert topic != HOOK_PREFIX


class TestHookSets:
    def test_hook_pipeline_contents(self) -> None:
        expected = {"pre_ingest", "post_ingest", "pre_search", "post_search", "pre_index", "post_index"}
        assert HOOK_PIPELINE == expected

    def test_hook_system_contents(self) -> None:
        expected = {"on_startup", "on_shutdown", "on_degraded", "on_restore"}
        assert HOOK_SYSTEM == expected

    def test_hook_cli_contents(self) -> None:
        expected = {"pre_command", "post_command"}
        assert HOOK_CLI == expected

    def test_all_hooks_union(self) -> None:
        assert ALL_HOOKS == HOOK_PIPELINE | HOOK_SYSTEM | HOOK_CLI
        assert len(ALL_HOOKS) == len(HOOK_PIPELINE) + len(HOOK_SYSTEM) + len(HOOK_CLI)

    def test_hook_sets_are_disjoint(self) -> None:
        assert HOOK_PIPELINE.isdisjoint(HOOK_SYSTEM)
        assert HOOK_PIPELINE.isdisjoint(HOOK_CLI)
        assert HOOK_SYSTEM.isdisjoint(HOOK_CLI)

    def test_all_hooks_frozenset(self) -> None:
        assert isinstance(ALL_HOOKS, frozenset)

    def test_hook_pipeline_frozenset(self) -> None:
        assert isinstance(HOOK_PIPELINE, frozenset)


# ═══════════════════════════════════════════════════════════════════════════════
# HookManager — Registration
# ═══════════════════════════════════════════════════════════════════════════════


class _HookablePlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()
        self.manifest = PluginManifest(name="hookable", hooks=["pre_ingest", "post_search"])
        self.pre_ingest_calls: list[Event] = []
        self.post_search_calls: list[Event] = []

    def execute(self, context: object) -> dict:
        return {}

    def on_pre_ingest(self, event: Event) -> Event | None:
        self.pre_ingest_calls.append(event)
        return event

    def on_post_search(self, event: Event) -> Event | None:
        self.post_search_calls.append(event)
        return event


class _FailingHookPlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()
        self.manifest = PluginManifest(name="failing", hooks=["pre_ingest"])
        self.count = 0

    def execute(self, context: object) -> dict:
        return {}

    def on_pre_ingest(self, event: Event) -> None:
        self.count += 1
        msg = f"fail #{self.count}"
        raise RuntimeError(msg)


class _CancelingPlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()
        self.manifest = PluginManifest(name="canceler", hooks=["pre_ingest"])

    def execute(self, context: object) -> dict:
        return {}

    def on_pre_ingest(self, event: Event) -> None:
        return None


class _UnknownHookPlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()
        self.manifest = PluginManifest(name="unknown", hooks=["nonexistent_hook"])

    def execute(self, context: object) -> dict:
        return {}


class _MissingMethodPlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()
        self.manifest = PluginManifest(name="missing", hooks=["pre_ingest"])

    def execute(self, context: object) -> dict:
        return {}
    # No on_pre_ingest method


class TestHookManagerRegistration:
    def test_register_creates_subscription(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 1
        assert bus.count(f"{HOOK_PREFIX}post_search") == 1

    def test_unregister_removes_subscription(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        hm.unregister_plugin_hooks("hookable")
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 0
        assert bus.count(f"{HOOK_PREFIX}post_search") == 0

    def test_register_twice_same_hook_creates_two(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        hm.register_plugin_hooks("hookable", plugin)
        # HookManager does not deduplicate — each register adds a subscription
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 2

    def test_register_unknown_hook_warns(self, bus: EventBus, degraded: DegradedMode, caplog: pytest.LogCaptureFixture) -> None:
        hm = HookManager(bus, degraded)
        plugin = _UnknownHookPlugin()
        hm.register_plugin_hooks("unknown", plugin)
        assert "hook desconocido" in caplog.text
        assert bus.count() == 0

    def test_register_missing_method_warns(self, bus: EventBus, degraded: DegradedMode, caplog: pytest.LogCaptureFixture) -> None:
        hm = HookManager(bus, degraded)
        plugin = _MissingMethodPlugin()
        hm.register_plugin_hooks("missing", plugin)
        assert "no implementa" in caplog.text
        assert bus.count() == 0

    def test_register_all_hook_categories(self, bus: EventBus, degraded: DegradedMode) -> None:
        class _AllHooksPlugin(PluginBase):
            def __init__(self) -> None:
                super().__init__()
                self.manifest = PluginManifest(name="all", hooks=list(ALL_HOOKS))

            def execute(self, context: object) -> dict:
                return {}

        # Dynamically create all hook methods
        for hook in ALL_HOOKS:
            method_name = f"on_{hook}"
            setattr(_AllHooksPlugin, method_name, lambda self, e: None)

        plugin = _AllHooksPlugin()
        hm = HookManager(bus, degraded)
        hm.register_plugin_hooks("all", plugin)
        assert bus.count() == len(ALL_HOOKS)

    def test_unregister_nonexistent_plugin(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        hm.unregister_plugin_hooks("nonexistent")  # should not raise

    def test_register_multiple_plugins(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        p1 = _HookablePlugin()
        p2 = _HookablePlugin()
        hm.register_plugin_hooks("p1", p1)
        hm.register_plugin_hooks("p2", p2)
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 2

    def test_unregister_one_plugin_keeps_other(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        p1 = _HookablePlugin()
        p2 = _HookablePlugin()
        hm.register_plugin_hooks("p1", p1)
        hm.register_plugin_hooks("p2", p2)
        hm.unregister_plugin_hooks("p1")
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 1


class TestHookManagerExecution:
    def test_hook_is_called(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(plugin.pre_ingest_calls) == 1

    def test_hook_receives_event(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert plugin.pre_ingest_calls[0].topic == f"{HOOK_PREFIX}pre_ingest"

    def test_hook_receives_payload(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        payload = HookEvent(plugin="test", hook="pre_ingest", context={"key": "val"})
        bus.publish(f"{HOOK_PREFIX}pre_ingest", payload)
        assert len(plugin.pre_ingest_calls) == 1
        assert isinstance(plugin.pre_ingest_calls[0].payload, HookEvent)

    def test_post_search_hook_called(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        bus.emit_sync(f"{HOOK_PREFIX}post_search", EventPayload())
        assert len(plugin.post_search_calls) == 1

    def test_hook_not_called_for_unrelated_topic(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        bus.emit_sync("unrelated.topic", EventPayload())
        assert len(plugin.pre_ingest_calls) == 0

    def test_hook_called_via_publish(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        bus.publish(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(plugin.pre_ingest_calls) == 1


class TestHookManagerCancellation:
    def test_canceling_hook_returns_none(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        plugin = _CancelingPlugin()
        hm.register_plugin_hooks("canceler", plugin)
        responses = bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert responses == [None]


class TestHookManagerExceptionIsolation:
    def test_failing_hook_does_not_break_other_hooks(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        good = _HookablePlugin()
        bad = _FailingHookPlugin()
        hm.register_plugin_hooks("hookable", good)
        hm.register_plugin_hooks("failing", bad)
        responses = bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(responses) == 2
        assert len(good.pre_ingest_calls) == 1

    def test_good_hook_returns_result(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        good = _HookablePlugin()
        hm.register_plugin_hooks("hookable", good)
        responses = bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert responses[0] is not None  # good hook returns the event


class TestHookManagerCircuitBreaker:
    def test_after_max_errors_hook_is_unsubscribed(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        bad = _FailingHookPlugin()
        hm.register_plugin_hooks("failing", bad)

        for _ in range(HOOK_MAX_ERRORS):
            bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())

        assert bad.count == HOOK_MAX_ERRORS
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 0

    def test_after_max_errors_future_calls_do_not_raise(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        bad = _FailingHookPlugin()
        hm.register_plugin_hooks("failing", bad)

        for _ in range(HOOK_MAX_ERRORS):
            bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())

        # After unsubscription, calls should not raise — no subscriber left
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())  # should not raise

    def test_degraded_mode_after_hook_failure(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        bad = _FailingHookPlugin()
        hm.register_plugin_hooks("failing", bad)
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert degraded.is_degraded("hook:failing:pre_ingest")

    def test_hook_recovers_after_successful_call(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        good = _HookablePlugin()
        hm.register_plugin_hooks("hookable", good)
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        key = "hook:hookable:pre_ingest"
        assert not degraded.is_degraded(key)

    def test_error_count_reset_after_success(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        good = _HookablePlugin()
        hm.register_plugin_hooks("hookable", good)
        # Call once, success -> error count 0
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(good.pre_ingest_calls) == 1
        # Call again, still works
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(good.pre_ingest_calls) == 2

    def test_hook_not_unsubscribed_below_max_errors(self, bus: EventBus, degraded: DegradedMode) -> None:
        hm = HookManager(bus, degraded)
        bad = _FailingHookPlugin()
        hm.register_plugin_hooks("failing", bad)

        for _ in range(HOOK_MAX_ERRORS - 1):
            bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())

        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 1  # still subscribed


# ═══════════════════════════════════════════════════════════════════════════════
# Compat — API Compatibility
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompatApiCompatibility:
    def test_exact_match(self) -> None:
        assert check_api_compatibility("1.0.0", "1.0.0") is True

    def test_minor_mismatch_compatible(self) -> None:
        assert check_api_compatibility("1.0.0", "1.1.0") is True

    def test_plugin_requires_newer_minor_incompatible(self) -> None:
        assert check_api_compatibility("1.5.0", "1.0.0") is False

    def test_major_mismatch_incompatible(self) -> None:
        assert check_api_compatibility("2.0.0", "1.0.0") is False

    def test_motor_newer_major_incompatible(self) -> None:
        assert check_api_compatibility("1.0.0", "2.0.0") is False

    def test_empty_plugin_version_with_legacy(self) -> None:
        assert check_api_compatibility("", "1.0.0", allow_legacy=True) is True

    def test_empty_plugin_version_without_legacy(self) -> None:
        assert check_api_compatibility("", "1.0.0", allow_legacy=False) is False

    def test_invalid_version_string(self) -> None:
        assert check_api_compatibility("abc", "1.0.0") is False

    def test_patch_version_ignored(self) -> None:
        assert check_api_compatibility("1.2.3", "1.2.0") is True
        assert check_api_compatibility("1.2.0", "1.2.3") is True

    def test_same_major_different_minor_compatible(self) -> None:
        assert check_api_compatibility("1.0.0", "1.2.0") is True
        assert check_api_compatibility("1.9.0", "1.9.0") is True

    def test_version_with_extra_parts(self) -> None:
        assert check_api_compatibility("1.0.0.rc1", "1.0.0") is False  # extra part


class TestCompatPluginDependency:
    def test_any_version_asterisk(self) -> None:
        assert check_plugin_dependency("dep", "*", "1.0.0") is True

    def test_any_version_empty(self) -> None:
        assert check_plugin_dependency("dep", "", "1.0.0") is True

    def test_greater_or_equal_satisfied(self) -> None:
        assert check_plugin_dependency("dep", ">=1.0.0", "1.5.0") is True
        assert check_plugin_dependency("dep", ">=1.0.0", "1.0.0") is True

    def test_greater_or_equal_not_satisfied(self) -> None:
        assert check_plugin_dependency("dep", ">=2.0.0", "1.5.0") is False

    def test_exact_match(self) -> None:
        assert check_plugin_dependency("dep", "==1.0.0", "1.0.0") is True

    def test_exact_mismatch(self) -> None:
        assert check_plugin_dependency("dep", "==1.0.0", "1.0.1") is False

    def test_less_than_satisfied(self) -> None:
        assert check_plugin_dependency("dep", "<2.0.0", "1.5.0") is True

    def test_less_than_not_satisfied(self) -> None:
        assert check_plugin_dependency("dep", "<2.0.0", "2.0.0") is False

    def test_range_satisfied(self) -> None:
        assert check_plugin_dependency("dep", ">=1.0.0<3.0.0", "2.0.0") is True

    def test_range_below(self) -> None:
        assert check_plugin_dependency("dep", ">=2.0.0<3.0.0", "1.0.0") is False

    def test_range_above(self) -> None:
        assert check_plugin_dependency("dep", ">=1.0.0<2.0.0", "3.0.0") is False

    def test_range_boundary_lower(self) -> None:
        assert check_plugin_dependency("dep", ">=1.0.0<2.0.0", "1.0.0") is True

    def test_compatible_operator_same_major_same_minor(self) -> None:
        assert check_plugin_dependency("dep", "~=1.0", "1.0.0") is True

    def test_compatible_operator_higher_minor(self) -> None:
        assert check_plugin_dependency("dep", "~=1.0", "1.5.0") is True

    def test_compatible_operator_different_major(self) -> None:
        assert check_plugin_dependency("dep", "~=1.0", "2.0.0") is False

    def test_invalid_spec_fallback_accept(self) -> None:
        assert check_plugin_dependency("dep", "???", "1.0.0") is True

    def test_non_semver_version(self) -> None:
        assert check_plugin_dependency("dep", ">=1.0.0", "abc") is False
