"""Tests para motor/observability/exporter.py — Fase 4 (B2)."""

from __future__ import annotations

from typing import Any

from motor.observability.exporter import _sanitize, format_prometheus


def _registry(snapshot: dict[str, list]) -> Any:
    return type("FakeRegistry", (), {"snapshot": lambda self: snapshot})()


class TestFormatPrometheus:
    def test_empty_snapshot(self) -> None:
        assert format_prometheus(_registry({})) == "\n"

    def test_counter_with_help_and_labels(self) -> None:
        reg = _registry({"counters": [{"name": "ura-requests", "description": "reqs", "labels": {"mode": "chat"}, "value": 3}]})
        out = format_prometheus(reg)
        assert "# HELP ura_requests reqs" in out
        assert "# TYPE ura_requests counter" in out
        assert 'ura_requests{mode="chat"} 3' in out

    def test_counter_without_help(self) -> None:
        out = format_prometheus(_registry({"counters": [{"name": "c", "value": 1}]}))
        assert "# TYPE c counter" in out
        assert "c 1" in out

    def test_gauge(self) -> None:
        reg = _registry({"gauges": [{"name": "g", "description": "gauge d", "labels": {}, "value": 7}]})
        out = format_prometheus(reg)
        assert "# TYPE g gauge" in out
        assert "g 7" in out

    def test_histogram_with_buckets(self) -> None:
        reg = _registry(
            {"histograms": [{"name": "h", "count": 5, "sum": 2.5, "buckets": {"0.1": 1, "1.0": 4}}]}
        )
        out = format_prometheus(reg)
        assert "h_count 5" in out
        assert "h_sum 2.5" in out
        assert 'h_bucket{le="0.1"} 1' in out
        assert 'h_bucket{le="1.0"} 4' in out

    def test_timer(self) -> None:
        reg = _registry({"timers": [{"name": "t", "description": "timer", "count": 2, "sum": 3.0, "buckets": {}}]})
        out = format_prometheus(reg)
        assert "# TYPE t histogram" in out
        assert "t_count 2" in out
        assert "t_sum 3.0" in out

    def test_labels_sorted(self) -> None:
        reg = _registry(
            {"counters": [{"name": "c", "labels": {"zeta": "1", "alfa": "2"}, "value": 1}]}
        )
        out = format_prometheus(reg)
        assert 'c{alfa="2",zeta="1"} 1' in out

    def test_sanitize_replaces_chars(self) -> None:
        assert _sanitize("a-b c.d") == "a_b_c_d"

    def test_help_omitted_when_empty(self) -> None:
        reg = _registry({"counters": [{"name": "c", "description": "", "labels": {}, "value": 1}]})
        out = format_prometheus(reg)
        assert "# HELP" not in out
