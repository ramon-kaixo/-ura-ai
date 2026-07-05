from __future__ import annotations

import time

import pytest

from motor.events.bus import EventBus
from motor.events.event import EventPayload, Event
from motor.events.topics import SYSTEM_STARTED, SYSTEM_SHUTDOWN


class TestEventBusPublish:
    def test_publish_calls_subscriber(self):
        bus = EventBus()
        received = []

        def cb(event):
            received.append(event)

        bus.subscribe("test.topic", cb)
        bus.publish("test.topic", EventPayload())
        assert len(received) == 1
        assert received[0].topic == "test.topic"

    def test_publish_passes_payload(self):
        bus = EventBus()
        received = []
        payload = EventPayload()

        def cb(event):
            received.append(event.payload)

        bus.subscribe("test.topic", cb)
        bus.publish("test.topic", payload)
        assert received[0] is payload

    def test_publish_does_not_call_unsubscribed(self):
        bus = EventBus()
        received = []
        sid = bus.subscribe("test.topic", lambda e: received.append(e))
        bus.unsubscribe(sid)
        bus.publish("test.topic", EventPayload())
        assert len(received) == 0

    def test_publish_isolates_exceptions(self):
        bus = EventBus()
        received = []

        def failing_cb(event):
            raise RuntimeError("fail")

        def good_cb(event):
            received.append(event)

        bus.subscribe("test.topic", failing_cb)
        bus.subscribe("test.topic", good_cb)
        bus.publish("test.topic", EventPayload())
        assert len(received) == 1


class TestEventBusSubscribe:
    def test_subscribe_returns_id(self):
        bus = EventBus()
        sid = bus.subscribe("t", lambda e: None)
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_subscribe_pattern_fnmatch(self):
        bus = EventBus()
        received = []
        bus.subscribe("pipeline.*", lambda e: received.append(e), pattern=True)
        bus.publish("pipeline.started", EventPayload())
        bus.publish("pipeline.failed", EventPayload())
        assert len(received) == 2

    def test_subscribe_pattern_no_match(self):
        bus = EventBus()
        received = []
        bus.subscribe("pipeline.*", lambda e: received.append(e), pattern=True)
        bus.publish("system.started", EventPayload())
        assert len(received) == 0


class TestEventBusUnsubscribe:
    def test_unsubscribe_removes_exact(self):
        bus = EventBus()
        received = []
        sid = bus.subscribe("t", lambda e: received.append(e))
        assert bus.unsubscribe(sid) is True
        bus.publish("t", EventPayload())
        assert len(received) == 0

    def test_unsubscribe_removes_pattern(self):
        bus = EventBus()
        received = []
        sid = bus.subscribe("p.*", lambda e: received.append(e), pattern=True)
        assert bus.unsubscribe(sid) is True
        bus.publish("p.x", EventPayload())
        assert len(received) == 0

    def test_unsubscribe_nonexistent_returns_false(self):
        bus = EventBus()
        assert bus.unsubscribe("nonexistent") is False

    def test_unsubscribe_twice_returns_false(self):
        bus = EventBus()
        sid = bus.subscribe("t", lambda e: None)
        bus.unsubscribe(sid)
        assert bus.unsubscribe(sid) is False


class TestEventBusPriority:
    def test_higher_priority_called_first(self):
        bus = EventBus()
        order = []

        bus.subscribe("t", lambda e: order.append(1), priority=10)
        bus.subscribe("t", lambda e: order.append(2), priority=5)
        bus.subscribe("t", lambda e: order.append(3), priority=0)

        bus.publish("t", EventPayload())
        assert order == [1, 2, 3]


class TestEventBusEmitSync:
    def test_emit_sync_returns_responses(self):
        bus = EventBus()
        bus.subscribe("t", lambda e: "response_a")
        bus.subscribe("t", lambda e: "response_b")
        responses = bus.emit_sync("t", EventPayload())
        assert responses == ["response_a", "response_b"]

    def test_emit_sync_exception_returns_none(self):
        bus = EventBus()
        bus.subscribe("t", lambda e: 42)
        bus.subscribe("t", lambda e: exec("raise ValueError('x')"))  # noqa: E202
        responses = bus.emit_sync("t", EventPayload())
        assert responses[0] == 42
        assert responses[1] is None


class TestEventBusCount:
    def test_count_initial(self):
        bus = EventBus()
        assert bus.count() == 0

    def test_count_after_subscribe(self):
        bus = EventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        assert bus.count() == 2

    def test_count_with_topic_filter(self):
        bus = EventBus()
        bus.subscribe("a.x", lambda e: None)
        bus.subscribe("a.y", lambda e: None)
        bus.subscribe("b.z", lambda e: None)
        assert bus.count("a.x") == 1
        assert bus.count("a.*") == 0  # exact match only


class TestEventBusReset:
    def test_reset_clears_all(self):
        bus = EventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b.*", lambda e: None, pattern=True)
        bus.reset()
        assert bus.count() == 0
        bus.publish("a", EventPayload())  # should not raise


class TestEventBusAsync:
    def test_publish_async_does_not_block(self):
        bus = EventBus()
        received = []

        def slow_cb(event):
            time.sleep(0.2)
            received.append(event)

        bus.subscribe("slow", slow_cb)
        start = time.monotonic()
        bus.publish_async("slow", EventPayload())
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # returns immediately
        time.sleep(0.3)
        assert len(received) == 1


class TestEventBusEventCreation:
    def test_event_auto_timestamp(self):
        event = Event(topic="t", payload=EventPayload())
        assert event.timestamp != ""

    def test_event_auto_id(self):
        event = Event(topic="t", payload=EventPayload())
        assert event.id != ""

    def test_event_frozen(self):
        event = Event(topic="t", payload=EventPayload())
        with pytest.raises(Exception):
            event.topic = "other"
