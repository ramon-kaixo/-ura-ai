"""Tests para motor/core/llm/router/strategy.py — retry, circuit breaker, fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

import motor.core.llm.router.strategy as strat
from motor.core.llm.router.strategy import call_with_fallback, call_with_retry


@pytest.fixture(autouse=True)
def _mock_metrics(monkeypatch):
    metrics = mock.Mock()
    monkeypatch.setattr("motor.core.llm.observability.metrics", metrics)
    yield metrics


class TestGetCb:
    def test_crea_si_no_existe(self, monkeypatch) -> None:
        cbs: dict = {}
        cb_cls = mock.Mock()
        monkeypatch.setattr("motor.core.llm.circuit_breaker.CircuitBreaker", cb_cls)
        out = strat._get_cb("p", cbs)
        assert out is cb_cls.return_value
        assert "p" in cbs

    def test_reusa(self) -> None:
        cbs = {"p": "ya"}
        assert strat._get_cb("p", cbs) == "ya"


class TestIsTransientError:
    def test_builtins(self) -> None:
        assert strat._is_transient_error(TimeoutError()) is True
        assert strat._is_transient_error(ConnectionError()) is True
        assert strat._is_transient_error(ValueError()) is False

    def test_httpx(self) -> None:
        import httpx

        assert strat._is_transient_error(httpx.ConnectError("c")) is True
        assert strat._is_transient_error(httpx.TimeoutException("t")) is True
        resp = httpx.Response(503, request=httpx.Request("GET", "http://x"))
        err = httpx.HTTPStatusError("e", request=resp.request, response=resp)
        assert strat._is_transient_error(err) is True
        resp2 = httpx.Response(400, request=httpx.Request("GET", "http://x"))
        err2 = httpx.HTTPStatusError("e", request=resp2.request, response=resp2)
        assert strat._is_transient_error(err2) is False

    def test_sin_httpx(self, monkeypatch) -> None:
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "httpx":
                raise ImportError("no")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert strat._is_transient_error(TimeoutError()) is True
        assert strat._is_transient_error(ValueError()) is False


class FakeCB:
    def __init__(self, state="CLOSED", available=True):
        self.state = SimpleNamespace(value=state)
        self.is_available = available

    def call(self, fn):
        return fn()

    def __call__(self, *a, **k):
        return self


class FakeMetrics:
    def __init__(self):
        self.records = []

    def record(self, *a, **k):
        self.records.append((a, k))


class TestCallWithRetry:
    def _setup(self, monkeypatch, prov_result=None, prov_error=None, state="CLOSED"):
        cb = FakeCB(state=state, available=state != "OPEN")
        cbs = {"p": cb}
        prov = mock.Mock()
        if prov_error:
            prov.generate.side_effect = prov_error
        else:
            prov.generate.return_value = prov_result
        metrics = FakeMetrics()
        monkeypatch.setattr("motor.core.llm.observability.metrics", metrics)
        return cb, cbs, prov, metrics

    def test_exito(self, monkeypatch) -> None:
        _cb, cbs, prov, metrics = self._setup(monkeypatch, prov_result="respuesta")
        r = call_with_retry(prov, "generate", "task", "p", None, cbs, prompt="hola")
        assert r == "respuesta"
        assert metrics.records  # success record

    def test_retry_deshabilitado(self, monkeypatch) -> None:
        _cb, cbs, prov, _metrics = self._setup(monkeypatch, prov_error=TimeoutError())
        monkeypatch.setattr(strat.time, "sleep", mock.Mock())
        r = call_with_retry(prov, "generate", "task", "p", None, cbs, retry_enabled=False)
        assert r.startswith("Error:")
        prov.generate.assert_called_once()

    def test_retry_transient(self, monkeypatch) -> None:
        _cb, cbs, prov, _metrics = self._setup(monkeypatch, prov_error=TimeoutError())
        sleep = mock.Mock()
        monkeypatch.setattr(strat.time, "sleep", sleep)
        r = call_with_retry(prov, "generate", "task", "p", None, cbs, retry_max_attempts=3)
        assert r.startswith("Error:")
        assert prov.generate.call_count == 3
        assert sleep.call_count == 2  # backoff entre intentos

    def test_error_no_transiente_sin_retry(self, monkeypatch) -> None:
        _cb, cbs, prov, _metrics = self._setup(monkeypatch, prov_error=ValueError("bad"))
        monkeypatch.setattr(strat.time, "sleep", mock.Mock())
        r = call_with_retry(prov, "generate", "task", "p", None, cbs, retry_max_attempts=3)
        assert r.startswith("Error:")
        prov.generate.assert_called_once()

    def test_sin_intentos_retorna_unknown(self, monkeypatch) -> None:
        _cb, cbs, prov, _metrics = self._setup(monkeypatch, prov_result="ok")
        monkeypatch.setattr(strat.time, "sleep", mock.Mock())
        r = call_with_retry(prov, "generate", "task", "p", None, cbs, retry_max_attempts=0)
        assert r == "Error: unknown"
        prov.generate.assert_not_called()

    def test_circuit_open(self, monkeypatch) -> None:

        class CbOpen:
            state = SimpleNamespace(value="OPEN")
            is_available = False

            def call(self, fn):
                raise __import__("motor.core.llm.circuit_breaker", fromlist=["CircuitBreakerOpenError"]).CircuitBreakerOpenError("p", 30.0)

        cbs = {"p": CbOpen()}
        prov = mock.Mock()
        metrics = FakeMetrics()
        monkeypatch.setattr("motor.core.llm.observability.metrics", metrics)
        r = call_with_retry(prov, "generate", "task", "p", None, cbs)
        assert r == "Error: circuit_breaker_open"

    def test_con_monitor(self, monkeypatch) -> None:
        _cb, cbs, prov, _metrics = self._setup(monkeypatch, prov_result="ok")
        monitor = mock.Mock()
        r = call_with_retry(prov, "generate", "task", "p", None, cbs, monitor=monitor)
        assert r == "ok"
        monitor.start_operation.assert_called_once()
        monitor.finish_operation.assert_called_once()

    def test_con_profiler_detector_baseline(self, monkeypatch) -> None:
        _cb, cbs, prov, _metrics = self._setup(monkeypatch, prov_result="ok")
        profiler = mock.Mock()
        profiler.stop.return_value = SimpleNamespace(wall_time_ms=10.0, cpu_time_ms=5.0, peak_memory_bytes=100)
        detector = mock.Mock()
        baseline = mock.Mock()
        r = call_with_retry(prov, "generate", "task", "p", None, cbs, profiler=profiler, detector=detector, baseline=baseline)
        assert r == "ok"
        profiler.start.assert_called_once()
        detector.evaluate_from_profile.assert_called_once()
        baseline.record.assert_called_once()


class TestCallWithFallback:
    def _reg(self, providers: dict):
        reg = mock.Mock()
        reg.list.return_value = list(providers)
        reg.get.side_effect = lambda n: providers[n]
        return reg

    def test_exito_primario(self, monkeypatch) -> None:
        cb = FakeCB()
        cbs = {"p": cb}
        prov = mock.Mock()
        prov.generate.return_value = "ok"
        reg = self._reg({"p": prov, "f": mock.Mock()})
        r, name = call_with_fallback(prov, "generate", "task", "p", reg, cbs, "hola")
        assert r == "ok"
        assert name == "p"

    def test_fallback_usa_segundo(self, monkeypatch) -> None:
        prim = mock.Mock()
        prim.generate.side_effect = [ValueError("bad"), ValueError("bad")]
        fall = mock.Mock()
        fall.generate.return_value = "ok"
        cbs = {"p": FakeCB(), "f": FakeCB()}
        reg = self._reg({"p": prim, "f": fall})
        r, name = call_with_fallback(prim, "generate", "task", "p", reg, cbs, "hola")
        assert r == "ok"
        assert name == "f"

    def test_fallback_deshabilitado(self, monkeypatch) -> None:
        prim = mock.Mock()
        prim.generate.side_effect = ValueError("bad")
        cbs = {"p": FakeCB()}
        reg = self._reg({"p": prim})
        r, name = call_with_fallback(prim, "generate", "task", "p", reg, cbs, fallback_enabled=False, retry_enabled=False)
        assert name == "p"
        assert r.startswith("Error:")

    def test_sin_fallbacks_disponibles(self, monkeypatch) -> None:
        prim = mock.Mock()
        prim.generate.side_effect = ValueError("bad")
        cbs = {"p": FakeCB()}
        reg = self._reg({"p": prim})
        _r, name = call_with_fallback(prim, "generate", "task", "p", reg, cbs, "hola")
        assert name == "p"

    def test_fallback_open_skip(self, monkeypatch) -> None:
        prim = mock.Mock()
        prim.generate.side_effect = ValueError("bad")
        fall = mock.Mock()
        cbs = {"p": FakeCB(), "f": FakeCB(state="OPEN", available=False)}
        reg = self._reg({"p": prim, "f": fall})
        _r, name = call_with_fallback(prim, "generate", "task", "p", reg, cbs, "hola")
        assert name == "p"  # fallback no disponible, sin intento

    def test_fallback_tambien_falla(self, monkeypatch) -> None:
        prim = mock.Mock()
        prim.generate.side_effect = ValueError("bad")
        fall = mock.Mock()
        fall.generate.side_effect = ValueError("bad")
        cbs = {"p": FakeCB(), "f": FakeCB()}
        reg = self._reg({"p": prim, "f": fall})
        r, name = call_with_fallback(prim, "generate", "task", "p", reg, cbs, "hola")
        assert name == "p"
        assert r.startswith("Error:")
