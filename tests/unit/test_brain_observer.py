"""Tests for BrainObserver (motor/brain/observer.py)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from motor.brain.observer import BrainObserver, HealthObservation


@pytest.fixture
def observer() -> BrainObserver:
    return BrainObserver()


class TestRegisterProvider:
    def test_register_adds_provider(self, observer: BrainObserver) -> None:
        fn = MagicMock(return_value={"status": "ok"})
        observer.register_provider("test", fn)
        assert len(observer._providers) == 1


class TestObserveAll:
    def test_observe_all_returns_list(self, observer: BrainObserver) -> None:
        observer.register_provider("test", MagicMock(return_value={"status": "ok"}))
        results = observer.observe_all()
        assert isinstance(results, list)
        assert len(results) == 1

    def test_observe_all_records_history(self, observer: BrainObserver) -> None:
        observer.register_provider("mem", MagicMock(return_value={"status": "ok", "latency_ms": 10}))
        observer.observe_all()
        assert "mem" in observer._history
        assert len(observer._history["mem"]) == 1

    def test_observe_provider_error(self, observer: BrainObserver) -> None:
        observer.register_provider("fail", MagicMock(side_effect=RuntimeError("crash")))
        results = observer.observe_all()
        assert results[0].status == "error"
        assert "crash" in (results[0].anomaly or "")


class TestAnalyze:
    def test_analyze_ok_status(self, observer: BrainObserver) -> None:
        obs = observer._analyze("test", {"status": "ok", "latency_ms": 10})
        assert obs.status == "ok"

    def test_analyze_latency_warning(self, observer: BrainObserver) -> None:
        obs = observer._analyze("test", {"status": "ok", "latency_ms": 600})
        assert obs.status == "warning"

    def test_analyze_latency_critical(self, observer: BrainObserver) -> None:
        obs = observer._analyze("test", {"status": "ok", "latency_ms": 1500})
        assert obs.status == "ok"
        assert obs.anomaly and "critical" in obs.anomaly.lower()


class TestGetCritical:
    def test_get_critical_empty(self, observer: BrainObserver) -> None:
        assert observer.get_critical() == []

    def test_get_critical_with_anomaly(self, observer: BrainObserver) -> None:
        observer._history["t"] = [
            HealthObservation(100, "t", "error", {}, "fail")
        ]
        critical = observer.get_critical()
        assert len(critical) == 1
