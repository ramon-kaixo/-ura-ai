"""Tests for motor/assistant/health.py — health registry wrapper."""

from __future__ import annotations

import pytest

from motor.observability.health import HealthRegistry


class TestAssistantHealth:
    @pytest.fixture(autouse=True)
    def _fresh_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.assistant.health as hmod
        monkeypatch.setattr(hmod, "_registry", HealthRegistry())
        self._mod = hmod

    def test_init_registers_all_components(self) -> None:
        self._mod.init_assistant_health()
        snapshot = self._mod.get_assistant_health().snapshot()
        components = snapshot.get("components", {})
        for c in ("llm", "memory", "rag", "conversation"):
            assert c in components

    def test_init_sets_all_healthy(self) -> None:
        self._mod.init_assistant_health()
        snapshot = self._mod.get_assistant_health().snapshot()
        for name, info in snapshot.get("components", {}).items():
            assert info.get("status") == "healthy"

    def test_set_healthy(self) -> None:
        self._mod.init_assistant_health()
        self._mod.get_assistant_health().set_healthy("llm", "test ok")
        snapshot = self._mod.get_assistant_health().snapshot()
        assert snapshot["components"]["llm"]["status"] == "healthy"

    def test_set_degraded(self) -> None:
        self._mod.init_assistant_health()
        self._mod.get_assistant_health().set_degraded("memory", "slow response")
        snapshot = self._mod.get_assistant_health().snapshot()
        assert snapshot["components"]["memory"]["status"] == "degraded"

    def test_set_unhealthy(self) -> None:
        self._mod.init_assistant_health()
        self._mod.get_assistant_health().set_unhealthy("rag", "connection failed")
        snapshot = self._mod.get_assistant_health().snapshot()
        assert snapshot["components"]["rag"]["status"] == "unhealthy"

    def test_check_health_alert_empty_when_healthy(self) -> None:
        self._mod.init_assistant_health()
        alerts = self._mod.check_health_alert()
        assert alerts == []

    def test_check_health_alert_detects_degraded(self) -> None:
        self._mod.init_assistant_health()
        self._mod.get_assistant_health().set_degraded("memory", "slow")
        alerts = self._mod.check_health_alert()
        assert any("memory" in a for a in alerts)

    def test_check_health_alert_detects_unhealthy(self) -> None:
        self._mod.init_assistant_health()
        self._mod.get_assistant_health().set_unhealthy("llm", "down")
        alerts = self._mod.check_health_alert()
        assert any("llm" in a for a in alerts)

    def test_get_assistant_health_returns_singleton(self) -> None:
        h1 = self._mod.get_assistant_health()
        h2 = self._mod.get_assistant_health()
        assert h1 is h2
