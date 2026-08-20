"""Cobertura 100x100 de observability + platform/resilience. TASK-20260820-015."""

from __future__ import annotations

import json
import logging
import random
import threading
import time

import pytest

from motor.observability.logging import (
    ContextFilter,
    JSONFormatter,
    get_correlation_id,
    get_workflow_id,
    set_correlation_id,
    set_workflow_id,
    setup_logging,
)
from motor.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    Timer,
    _TimerContext,
)
from motor.observability.metrics_labeled import (
    LabeledCounter,
    LabeledGauge,
    LabeledHistogram,
    PlatformMetrics,
    _label_key,
    get_platform_metrics,
)
from motor.observability.tracing_sampler import (
    MAX_TAGS_PER_EVENT,
    Sampler,
    SamplingStrategy,
    sanitize_tags,
)
from motor.platform.resilience import (
    Backpressure,
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    get_backpressure,
    get_circuit_breaker,
)

# ── tracing_sampler ──────────────────────────────────────────


def test_sampling_strategy_valores() -> None:
    assert SamplingStrategy.ALWAYS.value == "always"
    assert SamplingStrategy.PRIORITY.value == "priority"


def test_sampler_always() -> None:
    assert Sampler(strategy=SamplingStrategy.ALWAYS).should_sample() is True


def test_sampler_never() -> None:
    assert Sampler(strategy=SamplingStrategy.NEVER).should_sample() is False


def test_sampler_probabilistic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.05)
    assert Sampler(strategy=SamplingStrategy.PROBABILISTIC, probability=0.1).should_sample() is True
    monkeypatch.setattr(random, "random", lambda: 0.5)
    assert Sampler(strategy=SamplingStrategy.PROBABILISTIC, probability=0.1).should_sample() is False


def test_sampler_adaptive_sin_errores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.01)
    s = Sampler(strategy=SamplingStrategy.ADAPTIVE, adaptive_min_p=0.05)
    assert s.should_sample() is True  # p=0.05, random 0.01 < 0.05


def test_sampler_adaptive_con_errores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.01)
    s = Sampler(strategy=SamplingStrategy.ADAPTIVE)
    s._recent_errors = [True, True, True]  # rate=1.0 → p=max=1.0
    assert s.should_sample() is True
    s2 = Sampler(strategy=SamplingStrategy.ADAPTIVE)
    s2._recent_errors = [False, False, True]  # rate=0.33
    monkeypatch.setattr(random, "random", lambda: 0.99)
    assert s2.should_sample() is False  # p≈0.36 < 0.99


def test_sampler_priority() -> None:
    s = Sampler(strategy=SamplingStrategy.PRIORITY)
    assert s.should_sample({"priority": "critical"}) is True
    assert s.should_sample({"priority": "high"}) is True
    assert s.should_sample({"priority": "normal"}) is False
    assert s.should_sample(None) is False


def test_sampler_desconocido() -> None:
    s = Sampler(strategy="otro")  # type: ignore[assignment]
    assert s.should_sample() is True


def test_sampler_record_error() -> None:
    s = Sampler(error_rate_window=2)
    s.record_error(True)
    s.record_error(False)
    s.record_error(True)  # pop del primero
    assert len(s._recent_errors) == 2
    assert s._recent_errors == [False, True]


def test_sanitize_tags() -> None:
    tags = {"normal": "valor", "prompt_secreto": "x", "query": "y", "key_api": "z"}
    result = sanitize_tags(tags)
    assert result == {"normal": "valor"}


def test_sanitize_tags_truncation() -> None:
    tags = {"k" * 100: "v" * 500}
    result = sanitize_tags(tags)
    assert len(next(iter(result.keys()))) == 64
    assert len(next(iter(result.values()))) == 256


def test_sanitize_tags_max_32() -> None:
    tags = {f"tag{i}": "v" for i in range(50)}
    result = sanitize_tags(tags)
    assert len(result) == MAX_TAGS_PER_EVENT


def test_sanitize_tags_vacio() -> None:
    assert sanitize_tags({}) == {}


# ── logging ──────────────────────────────────────────────────


def test_json_formatter_basico() -> None:
    f = JSONFormatter(service="ura")
    record = logging.LogRecord("test.logger", logging.INFO, "f.py", 1, "mensaje", None, None)
    out = json.loads(f.format(record))
    assert out["level"] == "INFO"
    assert out["logger"] == "test.logger"
    assert out["message"] == "mensaje"
    assert out["service"] == "ura"
    assert "timestamp" in out


def test_json_formatter_con_excepcion() -> None:
    f = JSONFormatter()
    try:
        msg = "fallo"
        raise ValueError(msg)
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, "f.py", 1, "boom", None, __import__("sys").exc_info())
    out = json.loads(f.format(record))
    assert out["exception"]["type"] == "ValueError"
    assert "fallo" in out["exception"]["message"]


def test_json_formatter_extra_keys() -> None:
    f = JSONFormatter()
    record = logging.LogRecord("x", logging.INFO, "f.py", 1, "msg", None, None)
    record.extra_keys = {"correlation_id": "cid123"}
    out = json.loads(f.format(record))
    assert out["correlation_id"] == "cid123"


def test_json_formatter_extra_keys_no_dict() -> None:
    f = JSONFormatter()
    record = logging.LogRecord("x", logging.INFO, "f.py", 1, "msg", None, None)
    record.extra_keys = "no-dict"  # type: ignore[assignment]
    out = json.loads(f.format(record))
    assert out["message"] == "msg"  # sin extra_keys, no lanza


def test_correlation_id() -> None:
    cid = set_correlation_id()
    assert cid != ""
    assert get_correlation_id() == cid
    cid2 = set_correlation_id("explicito")
    assert cid2 == "explicito"


def test_correlation_id_thread_local() -> None:
    set_correlation_id("main")

    def _hilo() -> str:
        return get_correlation_id()  # sin cid en el hilo

    t = threading.Thread(target=lambda: _hilo())
    t.start()
    t.join()
    assert get_correlation_id() == "main"


def test_workflow_id() -> None:
    set_workflow_id("wf1")
    assert get_workflow_id() == "wf1"
    set_workflow_id("wf2")
    assert get_workflow_id() == "wf2"


def test_context_filter() -> None:
    set_correlation_id("cid-x")
    set_workflow_id("wf-y")
    f = ContextFilter()
    record = logging.LogRecord("x", logging.INFO, "f.py", 1, "m", None, None)
    assert f.filter(record) is True
    assert record.extra_keys == {"correlation_id": "cid-x", "workflow_id": "wf-y"}


def test_context_filter_sin_contexto() -> None:
    import motor.observability.logging as logmod

    class _Local:
        pass

    logmod._context = _Local()
    f = ContextFilter()
    record = logging.LogRecord("x", logging.INFO, "f.py", 1, "m", None, None)
    assert f.filter(record) is True
    assert record.extra_keys == {}
    logmod._context = __import__("threading").local()


def test_setup_logging_json() -> None:
    setup_logging(level="DEBUG", json_output=True, force=True)
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JSONFormatter)
    # cleanup
    root.handlers.clear()
    root.filters.clear()


def test_setup_logging_plain_fmt() -> None:
    setup_logging(level="INFO", json_output=False, fmt="%(message)s", force=True)
    root = logging.getLogger()
    assert root.handlers[0].formatter._fmt == "%(message)s"
    root.handlers.clear()
    root.filters.clear()


def test_setup_logging_plain_default() -> None:
    setup_logging(level="INFO", json_output=False, force=True)
    root = logging.getLogger()
    assert "%(asctime)s" in root.handlers[0].formatter._fmt
    root.handlers.clear()
    root.filters.clear()


def test_setup_logging_con_handlers() -> None:
    h = logging.StreamHandler()
    setup_logging(level="INFO", handlers=[h], force=True)
    root = logging.getLogger()
    assert h in root.handlers
    root.handlers.clear()
    root.filters.clear()


def test_setup_logging_sin_force() -> None:
    h = logging.StreamHandler()
    setup_logging(level="INFO", handlers=[h], force=False)
    root = logging.getLogger()
    assert h in root.handlers
    root.handlers.clear()
    root.filters.clear()


# ── metrics ──────────────────────────────────────────────────


def test_counter() -> None:
    c = Counter("requests", "desc", {"app": "ura"})
    c.inc()
    c.inc(3)
    assert c.get() == 4
    snap = c.snapshot()
    assert snap["type"] == "counter"
    assert snap["value"] == 4
    assert snap["labels"] == {"app": "ura"}


def test_gauge() -> None:
    g = Gauge("mem", "desc", {"x": "y"})
    g.set(10.0)
    g.inc(2.5)
    g.dec(1.5)
    assert g.get() == pytest.approx(11.0)
    assert g.snapshot()["type"] == "gauge"


def test_histogram() -> None:
    h = Histogram("lat", buckets=[0.1, 1.0])
    h.observe(0.05)
    h.observe(0.5)
    h.observe(5.0)
    snap = h.snapshot()
    assert snap["count"] == 3
    assert snap["buckets"]["0.1"] == 1
    assert snap["buckets"]["1.0"] == 2
    assert snap["buckets"]["+Inf"] == 3
    assert snap["sum"] == pytest.approx(5.55, abs=0.01)


def test_histogram_default_buckets() -> None:
    h = Histogram("lat")
    assert h._buckets == sorted([0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10])


def test_timer() -> None:
    t = Timer("op", "desc")
    with t.time():
        time.sleep(0.001)
    t.record(0.5)
    snap = t.snapshot()
    assert snap["type"] == "histogram"
    assert snap["count"] == 2


def test_timer_context() -> None:
    h = Histogram("h")
    ctx = _TimerContext(h)
    with ctx:
        time.sleep(0.001)
    assert h.snapshot()["count"] == 1


def test_metrics_registry() -> None:
    r = MetricsRegistry()
    c1 = r.counter("c1")
    c2 = r.counter("c1")  # mismo
    assert c1 is c2
    g1 = r.gauge("g1")
    g2 = r.gauge("g1")
    assert g1 is g2
    h1 = r.histogram("h1")
    h2 = r.histogram("h1")
    assert h1 is h2
    t1 = r.timer("t1")
    t2 = r.timer("t1")
    assert t1 is t2
    c1.inc()
    g1.set(5)
    h1.observe(0.2)
    t1.record(0.3)
    snap = r.snapshot()
    assert len(snap["counters"]) == 1
    assert len(snap["gauges"]) == 1
    assert len(snap["histograms"]) == 1  # solo h1 (timer usa Histogram interno no registrado)
    assert len(snap["timers"]) == 1


# ── metrics_labeled ──────────────────────────────────────────


def test_label_key() -> None:
    assert _label_key({"b": "2", "a": "1"}) == "a=1|b=2"


def test_labeled_counter() -> None:
    reg = MetricsRegistry()
    lc = LabeledCounter("req", "desc", registry=reg)
    lc.inc(source="web")
    lc.inc(2, source="web")
    lc.inc(source="api")
    assert reg.counter("req.source=web").get() == 3
    assert reg.counter("req.source=api").get() == 1


def test_labeled_histogram() -> None:
    reg = MetricsRegistry()
    lh = LabeledHistogram("dur", registry=reg)
    lh.observe(0.5, comp="a")
    lh.observe(1.5, comp="a")
    assert reg.histogram("dur.comp=a").snapshot()["count"] == 2


def test_labeled_gauge() -> None:
    reg = MetricsRegistry()
    lg = LabeledGauge("mem", registry=reg)
    lg.set(10.0, node="n1")
    lg.set(20.0, node="n1")
    assert reg.gauge("mem.node=n1").get() == 20.0


def test_platform_metrics_registro() -> None:
    pm = PlatformMetrics()
    pm.record_sent("src", "dst", "request", 1024, 12.5)
    pm.record_received("src", "dst", "request", 512)
    pm.record_error("src", "dst", "E001")
    pm.record_validation("src", 3.5)
    pm.record_negotiation(1.2)
    pm.record_health("svc", "ok", True)
    pm.record_health("svc2", "degraded", False)
    assert pm.messages_sent._counters  # hay counters
    assert pm.messages_received._counters
    assert pm.messages_error._counters
    assert pm.envelope_size._gauges
    assert pm.health_status._gauges


def test_get_platform_metrics_singleton() -> None:
    assert get_platform_metrics() is get_platform_metrics()


# ── platform/resilience ──────────────────────────────────────


def test_circuit_state_valores() -> None:
    assert CircuitState.CLOSED.value == "closed"
    assert CircuitState.HALF_OPEN.value == "half_open"


def test_circuit_breaker_open_error() -> None:
    e = CircuitBreakerOpenError("svc", 30.0)
    assert e.provider == "svc"
    assert e.retry_after == 30.0
    assert "svc" in str(e)


def test_circuit_breaker_ok() -> None:
    cb = CircuitBreaker("svc")
    assert cb.state == CircuitState.CLOSED
    assert cb.call(lambda: "resultado") == "resultado"
    assert cb._failure_count == 0
    assert cb.is_available is True


def test_circuit_breaker_abre_tras_umbral() -> None:
    cb = CircuitBreaker("svc", failure_threshold=2)

    def _falla():
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        cb.call(_falla)
    assert cb.state == CircuitState.CLOSED
    with pytest.raises(RuntimeError):
        cb.call(_falla)
    assert cb.state == CircuitState.OPEN
    assert cb._last_open_time > 0


def test_circuit_breaker_open_devuelve_none() -> None:
    cb = CircuitBreaker("svc", failure_threshold=1)

    def _falla():
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        cb.call(_falla)
    assert cb.state == CircuitState.OPEN
    assert cb.call(lambda: "x") is None  # OPEN → None


def test_circuit_breaker_half_open_tras_timeout() -> None:
    cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=0.05)

    def _falla():
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        cb.call(_falla)
    assert cb.state == CircuitState.OPEN
    time.sleep(0.1)
    assert cb.state == CircuitState.HALF_OPEN
    # éxito en half-open → cierra
    assert cb.call(lambda: "ok") == "ok"
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_props() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=30.0)
    assert cb._failure_threshold == 3
    assert cb._last_open_time == 0.0


def test_circuit_breaker_reset() -> None:
    cb = CircuitBreaker("svc", failure_threshold=1)

    def _falla():
        msg = "x"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        cb.call(_falla)
    assert cb.state == CircuitState.OPEN
    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


def test_backpressure_acquire_release() -> None:
    bp = Backpressure(max_queue=2, semaphore_count=2)
    assert bp.acquire() is True
    assert bp.acquire() is True
    assert bp.size == 2
    assert bp.full is True
    assert bp.acquire(timeout=0.01) is False  # cola llena
    bp.release()
    assert bp.size == 1
    assert bp.full is False


def test_backpressure_timeout() -> None:
    bp = Backpressure(max_queue=1, semaphore_count=0)  # sin permisos
    bp._sem = threading.Semaphore(0)
    assert bp.acquire(timeout=0.01) is False


def test_backpressure_cola_llena_release() -> None:
    bp = Backpressure(max_queue=1, semaphore_count=5)
    assert bp.acquire() is True
    assert bp.size == 1
    assert bp.acquire(timeout=0.01) is False  # cola llena → release interno
    assert bp.size == 1
    bp.release()
    assert bp.size == 0
    assert bp.acquire() is True  # ahora sí


def test_backpressure_release_min_0() -> None:
    bp = Backpressure()
    bp.release()  # sin acquire → no baja de 0
    assert bp.size == 0


def test_get_circuit_breaker_singleton() -> None:
    cb1 = get_circuit_breaker("svc-x")
    cb2 = get_circuit_breaker("svc-x")
    assert cb1 is cb2


def test_get_backpressure_singleton() -> None:
    bp1 = get_backpressure("bp-x")
    bp2 = get_backpressure("bp-x")
    assert bp1 is bp2
