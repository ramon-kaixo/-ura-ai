from __future__ import annotations


from motor.core.state import DegradedMode
from motor.events.bus import EventBus
from motor.events.event import EventPayload
from motor.events.hooks import HOOK_MAX_ERRORS, HookManager
from motor.events.topics import HOOK_PREFIX
from motor.plugin.base import PluginBase
from motor.plugin.manifest import PluginManifest


class _HookablePlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()
        self.manifest = PluginManifest(name="hookable", hooks=["pre_ingest", "post_search"])
        self.pre_ingest_calls: list = []
        self.post_search_calls: list = []

    def execute(self, context):
        return {}

    def on_pre_ingest(self, event):
        self.pre_ingest_calls.append(event)
        return event

    def on_post_search(self, event):
        self.post_search_calls.append(event)
        return event


class _FailingHookPlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()
        self.manifest = PluginManifest(name="failing", hooks=["pre_ingest"])
        self.count = 0

    def execute(self, context):
        return {}

    def on_pre_ingest(self, event):
        self.count += 1
        raise RuntimeError(f"fail #{self.count}")


class _CancelingPlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()
        self.manifest = PluginManifest(name="canceler", hooks=["pre_ingest"])

    def execute(self, context):
        return {}

    def on_pre_ingest(self, event):
        return None


class TestHookManagerRegistration:
    def test_register_creates_subscription(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 1
        assert bus.count(f"{HOOK_PREFIX}post_search") == 1

    def test_unregister_removes_subscription(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        hm.unregister_plugin_hooks("hookable")
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 0
        assert bus.count(f"{HOOK_PREFIX}post_search") == 0


class TestHookManagerExecution:
    def test_hook_is_called(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert len(plugin.pre_ingest_calls) == 1

    def test_hook_called_via_event_payload(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        plugin = _HookablePlugin()
        hm.register_plugin_hooks("hookable", plugin)
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert plugin.pre_ingest_calls[0].topic == f"{HOOK_PREFIX}pre_ingest"


class TestHookManagerCancellation:
    def test_canceling_hook_returns_none(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        plugin = _CancelingPlugin()
        hm.register_plugin_hooks("canceler", plugin)
        responses = bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert responses == [None]


class TestHookManagerExceptionIsolation:
    def test_failing_hook_does_not_break_other_hooks(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        good = _HookablePlugin()
        bad = _FailingHookPlugin()
        hm.register_plugin_hooks("hookable", good)
        hm.register_plugin_hooks("failing", bad)
        responses = bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        # First response is from good hook, second from failing (None)
        assert len(responses) == 2
        assert len(good.pre_ingest_calls) == 1


class TestHookManagerCircuitBreaker:
    def test_after_max_errors_hook_is_unsubscribed(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        bad = _FailingHookPlugin()
        hm.register_plugin_hooks("failing", bad)

        for _ in range(HOOK_MAX_ERRORS):
            bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())

        assert bad.count == HOOK_MAX_ERRORS
        assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 0

    def test_degraded_mode_after_hook_failure(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        bad = _FailingHookPlugin()
        hm.register_plugin_hooks("failing", bad)
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        assert dm.is_degraded("hook:failing:pre_ingest")

    def test_hook_recovers_after_successful_call(self):
        bus = EventBus()
        dm = DegradedMode()
        hm = HookManager(bus, dm)
        good = _HookablePlugin()
        hm.register_plugin_hooks("hookable", good)
        bus.emit_sync(f"{HOOK_PREFIX}pre_ingest", EventPayload())
        key = "hook:hookable:pre_ingest"
        assert not dm.is_degraded(key)
