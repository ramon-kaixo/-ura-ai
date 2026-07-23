"""Tests para motor/observability/prometheus_exporter.py."""
from motor.assistant.metrics import requests_total
from motor.observability.prometheus_exporter import export_metrics


def test_export_metrics_returns_string():
    result = export_metrics()
    assert isinstance(result, str)
    assert result.startswith("# URA metrics")


def test_export_contains_help_lines():
    result = export_metrics()
    assert "ura_requests_total" in result
    assert "ura_tokens_total" in result


def test_export_contains_counter_data():
    requests_total.inc(mode="test_prom", status="ok")
    result = export_metrics()
    assert "ura_requests_total" in result
