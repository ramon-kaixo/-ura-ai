"""Tests para F3 — Observabilidad del assistant."""

from __future__ import annotations

import json
import logging
import uuid

from motor.assistant.health import get_assistant_health, init_assistant_health
from motor.assistant.metrics import errors_total, request_latency, requests_total, tokens_total


def _counter_value(counter, **labels) -> int:
    key = "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
    if key in counter._counters:
        return counter._counters[key].snapshot()["value"]
    return 0


class TestHealthRegistry:
    def test_health_endpoint_returns_components(self) -> None:
        init_assistant_health()
        h = get_assistant_health()
        snapshot = h.snapshot()
        assert "components" in snapshot
        assert isinstance(snapshot["components"], dict)

    def test_health_has_all_components(self) -> None:
        init_assistant_health()
        h = get_assistant_health()
        components = h.snapshot().get("components", {})
        expected = {"llm", "memory", "rag", "conversation"}
        assert expected.issubset(components.keys()), f"Missing: {expected - set(components.keys())}"

    def test_health_status_changes(self) -> None:
        init_assistant_health()
        h = get_assistant_health()
        h.set_healthy("test_comp", "running")
        assert h.get_status("test_comp") == "healthy"
        h.set_degraded("test_comp", "slow")
        assert h.get_status("test_comp") == "degraded"
        h.set_unhealthy("test_comp", "down")
        assert h.get_status("test_comp") == "unhealthy"

    def test_health_unknown_component_returns_none(self) -> None:
        init_assistant_health()
        h = get_assistant_health()
        assert h.get_status("nonexistent") is None

    def test_health_snapshot_has_summary_keys(self) -> None:
        init_assistant_health()
        h = get_assistant_health()
        s = h.snapshot()
        for key in ("global", "healthy_count", "degraded_count", "unhealthy_count"):
            assert key in s, f"Missing summary key: {key}"

    def test_health_double_init_is_safe(self) -> None:
        init_assistant_health()
        h1 = get_assistant_health()
        init_assistant_health()
        h2 = get_assistant_health()
        assert h1 is h2


class TestMetrics:
    def test_counter_increments(self) -> None:
        requests_total.inc(mode="test_ci", status="ok")
        assert _counter_value(requests_total, mode="test_ci", status="ok") >= 1

    def test_counter_multiple_calls(self) -> None:
        requests_total.inc(mode="test_mc", status="ok")
        requests_total.inc(mode="test_mc", status="ok")
        assert _counter_value(requests_total, mode="test_mc", status="ok") >= 2

    def test_tokens_counter(self) -> None:
        tokens_total.inc(provider="test_tk", amount=42)
        assert _counter_value(tokens_total, provider="test_tk") >= 42

    def test_errors_counter(self) -> None:
        errors_total.inc(type="test_err", component="obs")
        assert _counter_value(errors_total, type="test_err", component="obs") >= 1

    def test_multiple_label_dimensions(self) -> None:
        requests_total.inc(mode="multi2", status="success")
        requests_total.inc(mode="multi2", status="error")
        assert _counter_value(requests_total, mode="multi2", status="success") >= 1
        assert _counter_value(requests_total, mode="multi2", status="error") >= 1

    def test_histogram_records_value(self) -> None:
        request_latency.observe(0.5, mode="test_h")
        key = "mode=test_h"
        assert key in request_latency._histograms
        snap = request_latency._histograms[key].snapshot()
        assert snap["count"] >= 1


class TestTracing:
    def test_trace_context_creates_span(self) -> None:
        from motor.observability.tracing_platform import TraceContext

        ctx = TraceContext(source="test", destination="obs")
        with ctx.span(message_type="test.span", tags={"key": "val"}):
            pass
        assert ctx.span_count == 1

    def test_trace_context_multiple_spans(self) -> None:
        from motor.observability.tracing_platform import TraceContext

        ctx = TraceContext(source="test", destination="obs")
        for _ in range(3):
            with ctx.span(message_type="test.loop"):
                pass
        assert ctx.span_count == 3

    def test_trace_context_error_span(self) -> None:
        from motor.observability.tracing_platform import TraceContext

        ctx = TraceContext(source="test", destination="obs")
        try:
            with ctx.span(message_type="test.error"):
                msg = "boom"
                raise ValueError(msg)
        except ValueError:
            pass
        assert ctx.error_count == 1

    def test_trace_context_correlation_id(self) -> None:
        from motor.observability.tracing_platform import TraceContext

        cid = str(uuid.uuid4())[:8]
        ctx = TraceContext(source="test", destination="obs", correlation_id=cid)
        assert ctx.correlation_id == cid


class TestLogging:
    def test_json_formatter_produces_json(self) -> None:
        from motor.observability.logging import JSONFormatter

        fmt = JSONFormatter(prefix="test")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="test message %s",
            args=("arg",),
            exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "test message arg"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["prefix"] == "test"

    def test_json_formatter_includes_timestamp(self) -> None:
        from motor.observability.logging import JSONFormatter

        fmt = JSONFormatter(prefix="test")
        record = logging.LogRecord("test", logging.INFO, "f.py", 1, "msg", (), None)
        output = json.loads(fmt.format(record))
        assert "timestamp" in output
        assert "T" in output["timestamp"]
