"""Tests para NotifierPlugin, CircuitBreaker y auto-healing."""
from __future__ import annotations

from unittest import mock

import pytest

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.notifier import NotifierPlugin


@pytest.fixture
def engine() -> PipelineEngine:
    return PipelineEngine()


class TestNotifier:
    def test_notify_critical_calls_webhook(self, engine):
        plugin = NotifierPlugin(engine)
        plugin.webhook_url = "http://mock.webhook"
        with mock.patch("httpx.post") as m:
            plugin.notify("critical", "test", "msg")
            m.assert_called_once()

    def test_notify_warning_skips_webhook(self, engine):
        plugin = NotifierPlugin(engine)
        plugin.webhook_url = "http://mock.webhook"
        with mock.patch("httpx.post") as m:
            plugin.notify("warning", "test", "msg")
            m.assert_not_called()

    def test_notify_without_url(self, engine):
        plugin = NotifierPlugin(engine)
        plugin.webhook_url = None
        with mock.patch("httpx.post") as m:
            result = plugin.notify("critical", "test", "msg")
            m.assert_not_called()
            assert result["sent"] is True

    def test_notify_logs_on_warning(self, engine):
        plugin = NotifierPlugin(engine)
        with mock.patch.object(engine.log, "info") as m:
            plugin.notify("warning", "test", "msg")
            m.assert_called_once()


class TestCircuitBreaker:
    def test_closed_calls_fn(self):
        from scripts.pro.tuneladora.resilience import CircuitBreaker

        cb = CircuitBreaker(max_failures=3)
        assert cb.call(lambda: "ok") == "ok"

    def test_opens_after_failures(self):
        from scripts.pro.tuneladora.resilience import CircuitBreaker

        cb = CircuitBreaker(max_failures=2, timeout=999)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail"))  # type: ignore
            )
        assert cb.state == "open"

    def test_open_raises(self):
        from scripts.pro.tuneladora.resilience import CircuitBreaker

        cb = CircuitBreaker(max_failures=1, timeout=999)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail"))  # type: ignore
            )
        with pytest.raises(RuntimeError, match="Circuit breaker OPEN"):
            cb.call(lambda: "ok")

    def test_reset(self):
        from scripts.pro.tuneladora.resilience import CircuitBreaker

        cb = CircuitBreaker(max_failures=1, timeout=999)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail"))  # type: ignore
            )
        assert cb.state == "open"
        cb.reset()
        assert cb.state == "closed"

    @mock.patch("time.time")
    def test_half_open_after_timeout(self, mock_time):
        from scripts.pro.tuneladora.resilience import CircuitBreaker

        mock_time.return_value = 100.0
        cb = CircuitBreaker(max_failures=1, timeout=60)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail"))  # type: ignore
            )
        assert cb.state == "open"
        mock_time.return_value = 200.0
        # Should be half-open now (60s passed)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail"))  # type: ignore
            )
        assert cb.state == "open"
