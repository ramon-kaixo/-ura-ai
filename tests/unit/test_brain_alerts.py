"""Tests for AlertEngine (motor/brain/alerts.py)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from motor.brain.alerts import Alert, AlertEngine
from motor.brain.observer import BrainObserver


@pytest.fixture
def observer() -> BrainObserver:
    return BrainObserver()


@pytest.fixture
def engine(observer: BrainObserver) -> AlertEngine:
    return AlertEngine(observer)


class TestEvaluate:
    def _add_provider(self, observer: BrainObserver, name: str, data: dict) -> None:
        observer.register_provider(name, MagicMock(return_value=data))

    def test_evaluate_provider_error(self, engine: AlertEngine, observer: BrainObserver) -> None:
        self._add_provider(observer, "ollama", {"status": "error", "anomaly": "connection refused"})
        alerts = engine.evaluate()
        critical = [a for a in alerts if a.severity == "critical"]
        assert any("ollama" in a.title.lower() for a in critical)

    def test_evaluate_disk_critical(self, engine: AlertEngine, observer: BrainObserver) -> None:
        self._add_provider(observer, "disk", {"status": "ok", "libre_gb": 5})
        alerts = engine.evaluate()
        emergency = [a for a in alerts if a.severity == "emergency"]
        assert len(emergency) >= 1
        assert "DISCO" in emergency[0].title

    def test_evaluate_disk_warning(self, engine: AlertEngine, observer: BrainObserver) -> None:
        self._add_provider(observer, "disk", {"status": "ok", "libre_gb": 30})
        alerts = engine.evaluate()
        warnings = [a for a in alerts if a.severity == "warning"]
        assert any("Disco" in a.title for a in warnings)

    def test_evaluate_latency_high(self, engine: AlertEngine, observer: BrainObserver) -> None:
        self._add_provider(observer, "llm", {"status": "ok", "latency_ms": 700})
        alerts = engine.evaluate()
        assert any("red" in a.title.lower() for a in alerts)

    def test_evaluate_degradation_multiple(self, engine: AlertEngine, observer: BrainObserver) -> None:
        self._add_provider(observer, "llm", {"status": "ok", "latency_ms": 600})
        self._add_provider(observer, "search", {"status": "ok", "latency_ms": 600})
        self._add_provider(observer, "db", {"status": "error", "anomaly": "fail"})
        alerts = engine.evaluate()
        assert any("DEGRADACION" in a.title for a in alerts)


class TestHistory:
    def test_get_history_returns_list(self, engine: AlertEngine) -> None:
        assert engine.get_history() == []

    def test_get_history_limit(self, engine: AlertEngine) -> None:
        engine._alert_history = [Alert("info", "t", "d", ["s"], 1.0) for _ in range(30)]
        assert len(engine.get_history(limit=10)) == 10

    def test_get_critical_filters(self, engine: AlertEngine) -> None:
        engine._alert_history = [
            Alert("info", "t1", "d1", ["s"], 1.0),
            Alert("critical", "t2", "d2", ["s"], 2.0),
            Alert("emergency", "t3", "d3", ["s"], 3.0),
        ]
        critical = engine.get_critical()
        assert len(critical) == 2
