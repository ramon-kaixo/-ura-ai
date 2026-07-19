from __future__ import annotations

import time

from motor.core.executor import SubprocessExecutor
from motor.events.bus import EventBus
from motor.events.event import EventPayload
from motor.observability.health import HealthRegistry
from motor.observability.instrumentation import Instrumentation
from motor.observability.metrics import Counter, Gauge, Histogram, MetricsRegistry, Timer
from motor.observability.readiness import ReadinessRegistry
from motor.pipeline.definition import PipelineDefinition, StageDefinition
from motor.pipeline.executor import PipelineExecutor
from motor.plugin.base import PluginBase
from motor.plugin.registry_v2 import PluginRegistryV2


class TestMetricsCounter:
    def test_inc(self):
        c = Counter("test")
        assert c.get() == 0
        c.inc()
        assert c.get() == 1
        c.inc(5)
        assert c.get() == 6

    def test_snapshot(self):
        c = Counter("cnt", "test counter", labels={"env": "test"})
        c.inc(3)
        s = c.snapshot()
        assert s["type"] == "counter"
        assert s["value"] == 3
        assert s["labels"] == {"env": "test"}


class TestMetricsGauge:
    def test_set(self):
        g = Gauge("test")
        g.set(42.5)
        assert g.get() == 42.5

    def test_inc_dec(self):
        g = Gauge("test")
        g.set(10)
        g.inc(5)
        assert g.get() == 15
        g.dec(3)
        assert g.get() == 12


class TestMetricsHistogram:
    def test_observe(self):
        h = Histogram("test", buckets=[0.1, 0.5, 1.0])
        h.observe(0.2)
        s = h.snapshot()
        assert s["count"] == 1
        assert s["buckets"]["0.1"] == 0
        assert s["buckets"]["0.5"] == 1
        assert s["buckets"]["+Inf"] == 1

    def test_multiple_observations(self):
        h = Histogram("test", buckets=[1, 5, 10])
        for v in [0.5, 2, 7, 12]:
            h.observe(v)
        s = h.snapshot()
        assert s["count"] == 4
        assert s["buckets"]["5"] == 2


class TestMetricsTimer:
    def test_record(self):
        t = Timer("test")
        t.record(0.5)
        s = t.snapshot()
        assert s["type"] == "histogram"
        assert s["count"] == 1

    def test_context_manager(self):
        t = Timer("ctx")
        with t.time():
            time.sleep(0.001)
        s = t.snapshot()
        assert s["count"] == 1
        assert s["sum"] > 0


class TestMetricsRegistry:
    def test_counter_singleton(self):
        reg = MetricsRegistry()
        c1 = reg.counter("req", labels={"a": "1"})
        c2 = reg.counter("req", labels={"b": "2"})
        assert c1 is c2  # same name = same object
        c1.inc()
        assert c2.get() == 1

    def test_gauge_singleton(self):
        reg = MetricsRegistry()
        g1 = reg.gauge("mem")
        g2 = reg.gauge("mem")
        assert g1 is g2

    def test_histogram_singleton(self):
        reg = MetricsRegistry()
        h1 = reg.histogram("latency", buckets=[1, 2])
        h2 = reg.histogram("latency")
        assert h1 is h2

    def timer_singleton(self):
        reg = MetricsRegistry()
        t1 = reg.timer("slow")
        t2 = reg.timer("slow")
        assert t1 is t2

    def test_snapshot_includes_all(self):
        reg = MetricsRegistry()
        reg.counter("c").inc()
        reg.gauge("g").set(1)
        reg.histogram("h").observe(0.5)
        reg.timer("t").record(0.2)
        s = reg.snapshot()
        assert len(s["counters"]) == 1
        assert len(s["gauges"]) == 1
        assert len(s["histograms"]) >= 1  # timer adds a histogram
        assert len(s["timers"]) == 1


class TestHealthRegistry:
    def test_initial_healthy(self):
        h = HealthRegistry()
        h.register_component("web")
        assert h.get_status("web") == "healthy"

    def test_set_degraded(self):
        h = HealthRegistry()
        h.register_component("db")
        h.set_degraded("db", "timeout")
        s = h.snapshot()
        assert s["global"] == "degraded"
        assert s["degraded_count"] == 1

    def test_set_unhealthy(self):
        h = HealthRegistry()
        h.register_component("disk")
        h.set_unhealthy("disk", "full")
        s = h.snapshot()
        assert s["global"] == "unhealthy"

    def test_healthy_takes_priority(self):
        h = HealthRegistry()
        h.register_component("a")
        h.register_component("b")
        h.set_degraded("a")
        h.set_healthy("a")
        s = h.snapshot()
        assert s["global"] == "healthy"

    def test_unhealthy_overrides_degraded(self):
        h = HealthRegistry()
        h.register_component("a")
        h.register_component("b")
        h.set_degraded("a")
        h.set_unhealthy("b")
        s = h.snapshot()
        assert s["global"] == "unhealthy"


class TestReadinessRegistry:
    def test_no_deps_ready(self):
        r = ReadinessRegistry()
        assert r.is_ready() is True

    def test_not_ready(self):
        r = ReadinessRegistry()
        r.register_dependency("qdrant")
        assert r.is_ready() is False

    def test_ready_after_set(self):
        r = ReadinessRegistry()
        r.register_dependency("qdrant")
        r.set_ready("qdrant")
        assert r.is_ready() is True

    def test_snapshot(self):
        r = ReadinessRegistry()
        r.register_dependency("db")
        r.set_not_ready("db", "down")
        s = r.snapshot()
        assert s["ready"] is False
        assert s["dependencies"]["db"]["reason"] == "down"


class TestInstrumentationEventBus:
    def test_records_metrics(self):
        bus = EventBus()
        ins = Instrumentation()
        bus = ins.instrument_eventbus(bus)

        received = []
        bus.subscribe("t", received.append)
        bus.publish("t", EventPayload())

        s = ins.metrics.snapshot()
        counters = {c["name"]: c for c in s["counters"]}
        assert counters["eventbus_published_total"]["value"] == 1
        assert counters["eventbus_published_total"]["labels"]["topic"] == "t"
        assert any("eventbus_publish_duration_seconds" in t["name"] for t in s["timers"])


class TestInstrumentationSubprocess:
    def test_records_metrics(self):
        executor = SubprocessExecutor()
        ins = Instrumentation()
        executor = ins.instrument_subprocess(executor)

        result = executor.run(["echo", "hello"])
        assert result.ok is True

        s = ins.metrics.snapshot()
        counters = {c["name"]: c for c in s["counters"]}
        assert counters["subprocess_started_total"]["value"] >= 1
        assert counters["subprocess_started_total"]["labels"]["cmd"] == "echo"


class TestInstrumentationPipeline:
    def test_records_pipeline_metrics(self):
        bus = EventBus()
        registry = PluginRegistryV2()
        executor = PipelineExecutor(registry, bus)
        ins = Instrumentation()

        plugin = _SimplePlugin("pipe_test")
        registry._instances["pipe_test"] = plugin
        registry._entries["pipe_test"] = None

        executor = ins.instrument_pipeline(executor)

        p = PipelineDefinition(name="bench", stages=[StageDefinition(name="s1", plugin="pipe_test")])
        result = executor.execute(p)
        assert result.ok is True

        s = ins.metrics.snapshot()
        counters = {c["name"]: c for c in s["counters"]}
        assert counters["pipeline_executed_total"]["value"] == 1
        assert counters["pipeline_completed_total"]["value"] == 1


class TestInstrumentationHealth:
    def test_components_registered(self):
        bus = EventBus()
        ins = Instrumentation()
        ins.instrument_eventbus(bus)
        h = ins.health.snapshot()
        assert "eventbus" in h["components"]
        assert h["components"]["eventbus"]["status"] == "healthy"


class _SimplePlugin(PluginBase):
    def __init__(self, name: str = "simple") -> None:
        super().__init__()
        self.executed = False

    def execute(self, context=None):
        self.executed = True
        return {"result": "ok"}
