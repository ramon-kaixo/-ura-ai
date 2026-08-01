"""Tests para motor/assistant/metrics.py — Fase 4 (B2).

Los contadores son singletons de módulo: los tests los reemplazan con
instancias frescas via monkeypatch para no contaminar estado global.
"""

from __future__ import annotations

import logging

import pytest

import motor.assistant.metrics as metrics_mod
from motor.assistant.metrics import check_error_alert, check_latency_alert
from motor.observability.metrics_labeled import LabeledCounter, LabeledHistogram


@pytest.fixture(autouse=True)
def _fresh_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics_mod, "requests_total", LabeledCounter("t_requests"))
    monkeypatch.setattr(metrics_mod, "errors_total", LabeledCounter("t_errors"))
    monkeypatch.setattr(metrics_mod, "request_latency", LabeledHistogram("t_latency", buckets=(1.0, 5.0)))
    monkeypatch.setattr(metrics_mod, "tokens_total", LabeledCounter("t_tokens"))


class TestCheckLatencyAlert:
    def test_no_alerts_when_below_threshold(self, caplog: pytest.LogCaptureFixture) -> None:
        metrics_mod.request_latency.observe(0.5, mode="chat")
        with caplog.at_level(logging.WARNING):
            assert check_latency_alert(threshold=5.0) == []

    def test_alert_when_avg_above_threshold(self, caplog: pytest.LogCaptureFixture) -> None:
        metrics_mod.request_latency.observe(9.0, mode="chat")
        alerts = check_latency_alert(threshold=5.0)
        assert len(alerts) == 1
        assert "LATENCY ALERT" in alerts[0]
        assert "chat" in alerts[0]

    def test_alert_only_for_exceeding_keys(self) -> None:
        metrics_mod.request_latency.observe(9.0, mode="lento")
        metrics_mod.request_latency.observe(0.1, mode="rapido")
        alerts = check_latency_alert(threshold=5.0)
        assert len(alerts) == 1
        assert "lento" in alerts[0]

    def test_empty_state_no_alerts(self) -> None:
        assert check_latency_alert() == []


class TestCheckErrorAlert:
    def test_no_alerts_low_rate(self) -> None:
        metrics_mod.requests_total.inc(100, mode="chat")
        metrics_mod.errors_total.inc(1, type="llm")
        assert check_error_alert(threshold=0.1) == []

    def test_alert_high_rate(self) -> None:
        metrics_mod.requests_total.inc(10, mode="chat")
        metrics_mod.errors_total.inc(5, type="llm")
        alerts = check_error_alert(threshold=0.1)
        assert len(alerts) == 1
        assert "ERROR RATE ALERT" in alerts[0]
        assert "5/10" in alerts[0]

    def test_empty_state_no_alerts(self) -> None:
        assert check_error_alert() == []

    def test_errors_accumulate_across_labels(self) -> None:
        metrics_mod.requests_total.inc(10, mode="chat")
        metrics_mod.errors_total.inc(2, type="llm")
        metrics_mod.errors_total.inc(2, type="timeout")
        alerts = check_error_alert(threshold=0.1)
        assert len(alerts) == 1
