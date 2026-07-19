from __future__ import annotations

import json
import logging

from motor.observability.exporter import format_prometheus
from motor.observability.logging import (
    ContextFilter,
    JSONFormatter,
    get_correlation_id,
    get_workflow_id,
    set_correlation_id,
    set_workflow_id,
)
from motor.observability.metrics import MetricsRegistry


class TestJSONLogging:
    def test_json_formatter(self):
        logger = logging.getLogger("test_json")
        logger.handlers.clear()
        handler = logging.StreamHandler()
        fmt = JSONFormatter()
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.info("hello")
        # Should not raise
        assert True

    def test_json_has_timestamp(self):
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        fmt = JSONFormatter()
        output = fmt.format(record)
        data = json.loads(output)
        assert "timestamp" in data
        assert data["message"] == "msg"

    def test_json_serializes_exception(self):
        import sys

        try:
            msg = "test error"
            raise ValueError(msg)
        except ValueError:
            exc_info = sys.exc_info()
        record = logging.LogRecord("test", logging.ERROR, "", 0, "fail", (), exc_info=exc_info)
        fmt = JSONFormatter()
        output = fmt.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"


class TestCorrelationID:
    def test_set_and_get(self):
        cid = set_correlation_id()
        assert get_correlation_id() == cid
        assert len(cid) == 12

    def test_custom_id(self):
        set_correlation_id("my_custom_id")
        assert get_correlation_id() == "my_custom_id"

    def test_empty_default(self):
        import motor.observability.logging as obs_logging

        obs_logging._context.correlation_id = ""  # noqa: SLF001
        assert get_correlation_id() == ""

    def test_workflow_id(self):
        set_workflow_id("wf_001")
        assert get_workflow_id() == "wf_001"

    def test_context_filter_adds_ids(self):
        set_correlation_id("cid_test")
        set_workflow_id("wid_test")
        record = logging.LogRecord("test", logging.INFO, "", 0, "test", (), None)
        f = ContextFilter()
        assert f.filter(record)
        assert record.extra_keys["correlation_id"] == "cid_test"
        assert record.extra_keys["workflow_id"] == "wid_test"


class TestPrometheusExporter:
    def test_format_counter(self):
        reg = MetricsRegistry()
        c = reg.counter("ura_test_total", "Test counter", labels={"env": "test"})
        c.inc(3)
        output = format_prometheus(reg)
        assert "ura_test_total" in output
        assert "counter" in output
        assert 'env="test"' in output

    def test_format_gauge(self):
        reg = MetricsRegistry()
        g = reg.gauge("ura_temperature", "Test gauge")
        g.set(36.5)
        output = format_prometheus(reg)
        assert "ura_temperature" in output
        assert "gauge" in output

    def test_format_histogram(self):
        reg = MetricsRegistry()
        h = reg.histogram("ura_duration_ms", "Test histogram", buckets=[1, 5, 10])
        h.observe(3)
        output = format_prometheus(reg)
        assert "ura_duration_ms_count" in output
        assert "ura_duration_ms_sum" in output
        assert '_bucket{le="5"}' in output

    def test_format_timer(self):
        reg = MetricsRegistry()
        t = reg.timer("ura_slow_op", "Test timer")
        t.record(0.5)
        output = format_prometheus(reg)
        assert "ura_slow_op_count" in output

    def test_empty_registry(self):
        reg = MetricsRegistry()
        output = format_prometheus(reg)
        assert output.endswith("\n")

    def test_sanitizes_names(self):
        reg = MetricsRegistry()
        reg.counter("ura.test-metric", "Test")
        output = format_prometheus(reg)
        assert "ura_test_metric" in output
        assert "ura.test-metric" not in output

    def test_valid_prometheus_syntax(self):
        reg = MetricsRegistry()
        reg.counter("ura_requests_total").inc()
        reg.gauge("ura_temp").set(1)
        output = format_prometheus(reg)
        for line in output.splitlines():
            if line and not line.startswith("#"):
                assert " " in line, f"Invalid prom line: {line}"


class TestMetricsThreadSafety:
    def test_concurrent_counters(self):
        import concurrent.futures

        reg = MetricsRegistry()
        c = reg.counter("ura_concurrent")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
            futures = [exe.submit(c.inc) for _ in range(100)]
            concurrent.futures.wait(futures)
        assert c.get() == 100

    def test_concurrent_histogram(self):
        import concurrent.futures

        reg = MetricsRegistry()
        h = reg.histogram("ura_concurrent_hist")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
            futures = [exe.submit(h.observe, 1.0) for _ in range(100)]
            concurrent.futures.wait(futures)
        snap = h.snapshot()
        assert snap["count"] == 100


class TestDashboard:
    def test_dashboard_valid_json(self):
        import json

        with open("deploy/grafana/dashboard.json") as f:  # noqa: PTH123
            data = json.load(f)
        assert "title" in data
        assert "panels" in data
        assert len(data["panels"]) > 0

    def test_dashboard_has_ura_tag(self):
        import json

        with open("deploy/grafana/dashboard.json") as f:  # noqa: PTH123
            data = json.load(f)
        assert "ura" in data.get("tags", [])


class TestAlertRules:
    def test_alerts_valid_yaml(self):
        import yaml

        with open("deploy/prometheus/alerts.yml") as f:  # noqa: PTH123
            data = yaml.safe_load(f)
        assert "groups" in data
        assert len(data["groups"]) > 0

    def test_alerts_have_names(self):
        import yaml

        with open("deploy/prometheus/alerts.yml") as f:  # noqa: PTH123
            data = yaml.safe_load(f)
        for group in data["groups"]:
            for rule in group.get("rules", []):
                assert "alert" in rule
                assert "expr" in rule
