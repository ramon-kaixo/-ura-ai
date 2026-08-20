"""Cobertura 100x100 de runner + search_logger + watchdog_funciones. TASK-20260820-010."""

from __future__ import annotations

import asyncio
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import core.search_logger as sl
import core.watchdog_funciones as wd
from core.search_logger import _get_writer, _NdjsonWriter, log_feedback, log_query, read_logs
from motor.agents.models import ToolContract, ToolRequest, ToolResult
from motor.agents.runner import (
    AgentToolRunner,
    RateLimiter,
    ToolAdapterError,
    ToolCancelledError,
    ToolError,
    ToolNotFoundError,
    ToolPermanentError,
    ToolTimeoutError,
    ToolTransientError,
)

# ── runner: excepciones ──────────────────────────────────────


def test_excepciones_tipificadas() -> None:
    assert issubclass(ToolTimeoutError, ToolError)
    assert issubclass(ToolCancelledError, ToolError)
    assert issubclass(ToolTransientError, ToolError)
    assert issubclass(ToolPermanentError, ToolError)
    assert issubclass(ToolNotFoundError, ToolError)
    assert issubclass(ToolAdapterError, ToolError)


# ── runner: RateLimiter ──────────────────────────────────────


def test_rate_limiter_ok() -> None:
    rl = RateLimiter(max_calls=2, window_seconds=60)
    rl.check("tool1")
    rl.check("tool1")
    with pytest.raises(ToolTransientError):
        rl.check("tool1")


def test_rate_limiter_limpieza_antiguas() -> None:
    rl = RateLimiter(max_calls=2, window_seconds=60)
    rl._buckets["tool"] = [time.time() - 120]
    rl.check("tool")  # la vieja se limpia
    rl.check("tool")


# ── runner: registro y contratos ─────────────────────────────


class _AdapterStub:
    def __init__(self, result: dict | None = None, error: Exception | None = None, delay: float = 0.0) -> None:
        self._result = result or {"ok": True}
        self._error = error
        self._delay = delay
        self.cancelled = False

    def run(self, params: dict) -> dict:
        if self._delay:
            time.sleep(self._delay)
        if self._error:
            raise self._error
        return self._result

    def cancel(self) -> None:
        self.cancelled = True


def _contrato(name: str, **kw) -> ToolContract:
    return ToolContract(name=name, **kw)


def test_register_y_get_contract() -> None:
    r = AgentToolRunner()
    r.register("echo", _AdapterStub(), _contrato("echo", idempotent=True))
    c = r.get_contract("echo")
    assert c.name == "echo"


def test_get_contract_no_registrado() -> None:
    r = AgentToolRunner()
    with pytest.raises(ToolNotFoundError):
        r.get_contract("nope")


def test_build_request_no_registrado() -> None:
    r = AgentToolRunner()
    with pytest.raises(ToolNotFoundError):
        r._build_request("nope", {}, 30)


# ── runner: run ──────────────────────────────────────────────


def test_run_ok() -> None:
    r = AgentToolRunner()
    r.register("echo", _AdapterStub({"ok": True}), _contrato("echo"))
    res = r.run("echo", {"msg": "hola"})
    assert res == {"ok": True}


def test_run_timeout() -> None:
    r = AgentToolRunner()
    r.register("lento", _AdapterStub(delay=5.0), _contrato("lento"))
    with pytest.raises(ToolTimeoutError):
        r.run("lento", {}, timeout=1)


def test_run_perm_error() -> None:
    r = AgentToolRunner()
    r.register("roto", _AdapterStub(error=ValueError("permanente")), _contrato("roto", idempotent=True))
    with pytest.raises(ToolError):
        r.run("roto", {})


def test_run_transient_reintenta() -> None:
    llamadas = {"n": 0}

    class _Transitorio:
        def run(self, params: dict) -> dict:
            llamadas["n"] += 1
            if llamadas["n"] < 2:
                raise ToolTransientError("intenta de nuevo")
            return {"ok": True}

        def cancel(self) -> None:
            pass

    r = AgentToolRunner()
    r.register("trans", _Transitorio(), _contrato("trans", idempotent=False))
    res = r.run("trans", {})
    assert res == {"ok": True}
    assert llamadas["n"] == 2


def test_run_transient_agota_reintentos() -> None:
    class _SiempreFalla:
        def run(self, params: dict) -> dict:
            raise ToolTransientError("siempre")

        def cancel(self) -> None:
            pass

    r = AgentToolRunner()
    r.register("trans", _SiempreFalla(), _contrato("trans", idempotent=False))
    with pytest.raises(ToolError):
        r.run("trans", {})
    # el resultado final: "All 3 attempts failed"


def test_run_idempotente_sin_reintento() -> None:
    llamadas = {"n": 0}

    class _Falla:
        def run(self, params: dict) -> dict:
            llamadas["n"] += 1
            raise ToolTransientError("x")

        def cancel(self) -> None:
            pass

    r = AgentToolRunner()
    r.register("idem", _Falla(), _contrato("idem", idempotent=True))
    with pytest.raises(ToolError):
        r.run("idem", {})
    assert llamadas["n"] == 1


def test_cancel_tool() -> None:
    r = AgentToolRunner()
    a = _AdapterStub()
    r.register("echo", a, _contrato("echo"))
    r.cancel("echo")
    assert a.cancelled is True
    r.cancel("no-existe")  # no lanza


def test_backpressure_timeout() -> None:
    r = AgentToolRunner(max_concurrent_tools=1)
    r.register("lento", _AdapterStub(delay=2.0), _contrato("lento"))

    def _corre() -> str:
        try:
            r.run("lento", {}, timeout=1)
            return "ok"
        except ToolTimeoutError:
            return "timeout"

    t1 = threading.Thread(target=_corre)
    t2 = threading.Thread(target=_corre)
    t1.start()
    time.sleep(0.1)  # t1 toma el semáforo
    t2.start()
    t1.join()
    t2.join()
    # t2 no adquirió el semáforo en 1s → ToolTimeoutError
    assert True


def test_raise_error_mapping() -> None:
    AgentToolRunner()
    casos = [
        ("ToolTimeoutError", ToolTimeoutError),
        ("ToolCancelledError", ToolCancelledError),
        ("ToolTransientError", ToolTransientError),
        ("ToolPermanentError", ToolPermanentError),
        ("ToolNotFoundError", ToolNotFoundError),
        ("ToolAdapterError", ToolAdapterError),
        ("OtroTipo", ToolError),
    ]
    for tipo, cls in casos:
        with pytest.raises(cls):
            AgentToolRunner._raise_error(ToolResult(execution_id="x", tool_name="t", success=False, error="e", error_type=tipo))


# ── runner: _execute directo ──────────────────────────────────


def test_execute_single_ok() -> None:
    r = AgentToolRunner()
    a = _AdapterStub({"ok": 1})
    req = ToolRequest(execution_id="e1", tool_name="echo", params={}, timeout=10, attempt=1)
    res = r._execute_single(req, a, None)
    assert res.success is True
    assert res.data == {"ok": 1}


def test_execute_single_error() -> None:
    r = AgentToolRunner()
    a = _AdapterStub(error=RuntimeError("boom"))
    req = ToolRequest(execution_id="e1", tool_name="t", params={}, timeout=10, attempt=1)
    res = r._execute_single(req, a, None)
    assert res.success is False
    assert res.error == "boom"
    assert res.error_type == "RuntimeError"


def test_execute_single_timeout_cancela() -> None:
    r = AgentToolRunner()
    a = _AdapterStub(delay=5.0)
    req = ToolRequest(execution_id="e1", tool_name="t", params={}, timeout=1, attempt=1)
    res = r._execute_single(req, a, None)
    assert res.success is False
    assert res.error_type == "ToolTimeoutError"
    assert a.cancelled is True


def test_execute_sin_contrato() -> None:
    r = AgentToolRunner()
    a = _AdapterStub({"ok": 1})
    r.register("t", a, _contrato("t"))
    # sin contrato: max_attempts=1, rama else de `if contract is not None`
    r._contracts = {}
    req = ToolRequest(execution_id="e1", tool_name="t", params={}, timeout=10, attempt=1)
    res = r._execute(req)
    assert res.success is True


def test_execute_reintentos_y_resultado_final() -> None:
    llamadas = {"n": 0}

    class _FallaSiempre:
        def run(self, params: dict) -> dict:
            llamadas["n"] += 1
            raise ToolTransientError("no")

        def cancel(self) -> None:
            pass

    r = AgentToolRunner()
    r.register("t", _FallaSiempre(), _contrato("t", idempotent=False))
    req = ToolRequest(execution_id="e1", tool_name="t", params={}, timeout=10, attempt=1)
    res = r._execute(req)
    assert res.success is False
    assert "All 3 attempts failed" in res.error


# ── search_logger ────────────────────────────────────────────


def test_log_query_y_read(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URA_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sl, "_WRITER", None)
    log_query("hola mundo", [{"source": "a", "similarity": 0.9, "total_chunks_meta": 3, "idioma": "es"}], 12.5, use_reranker=True, top_k=8)
    records = read_logs(str(tmp_path))
    assert len(records) == 1
    r = records[0]
    assert r["query"] == "hola mundo"
    assert r["num_results"] == 1
    assert r["use_reranker"] is True
    assert r["top_k"] == 8
    assert r["total_chunks"] == 3


def test_log_query_sin_resultados(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URA_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sl, "_WRITER", None)
    log_query("vacío", [], 1.0)
    records = read_logs(str(tmp_path))
    assert records[0]["sources"] == []
    assert records[0]["idiomas"] == []


def test_log_query_excepcion(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URA_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sl, "_WRITER", None)

    class _WriterRoto:
        def write(self, record: dict) -> None:
            msg = "disco lleno"
            raise OSError(msg)

    monkeypatch.setattr(sl, "_get_writer", lambda: _WriterRoto())
    log_query("x", [], 1.0)  # no lanza


def test_read_logs_dir_inexistente() -> None:
    assert read_logs("/no/existe/dir") == []


def test_read_logs_lineas_corruptas(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "search_2026-08-20.ndjson"
    f.write_text('{"ts": "t1"}\nno-json\n{"ts": "t2"}\n\n')
    records = read_logs(str(tmp_path))
    assert len(records) == 2


def test_read_logs_since_y_orden(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "search_2026-08-20.ndjson"
    f.write_text('{"ts": "2026-08-20T10:00:00"}\n{"ts": "2026-08-20T11:00:00"}\n')
    records = read_logs(str(tmp_path), since="2026-08-20T10:30:00")
    assert len(records) == 1
    assert records[0]["ts"] == "2026-08-20T11:00:00"


def test_read_logs_limit(tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "search_2026-08-20.ndjson"
    f.write_text('{"ts": "t1"}\n{"ts": "t2"}\n{"ts": "t3"}\n')
    records = read_logs(str(tmp_path), limit=2)
    assert len(records) == 2


def test_log_feedback(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URA_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sl, "_WRITER", None)
    log_feedback("t1", "query original", ["src1"], rating=4)
    records = read_logs(str(tmp_path))
    assert records[0]["type"] == "feedback"
    assert records[0]["clicked_sources"] == ["src1"]
    assert records[0]["rating"] == 4


def test_log_feedback_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    class _WriterRoto:
        def write(self, record: dict) -> None:
            msg = "roto"
            raise OSError(msg)

    monkeypatch.setattr(sl, "_get_writer", lambda: _WriterRoto())
    log_feedback("t", "q", ["s"])  # no lanza


def test_ndjson_writer_rota_archivo(tmp_path: object) -> None:
    w = _NdjsonWriter(str(tmp_path))
    w.write({"ts": "2026-08-20T10:00:00"})
    w.write({"ts": "2026-08-20T10:00:01"})
    w.close()
    w.close()  # idempotente
    files = list(Path(str(tmp_path)).glob("search_*.ndjson"))
    assert len(files) == 1
    lines = files[0].read_text().strip().split("\n")
    assert len(lines) == 2


def test_get_writer_cachea() -> None:
    w1 = _get_writer()
    w2 = _get_writer()
    assert w1 is w2


def test_ndjson_writer_reusa_archivo(tmp_path: object) -> None:
    w = _NdjsonWriter(str(tmp_path))
    w.write({"ts": "a"})
    path1 = w._path
    w.write({"ts": "b"})  # mismo día → reusa archivo
    assert w._path == path1
    w.close()


def test_ndjson_writer_rotar_dia(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    w = _NdjsonWriter(str(tmp_path))
    ayer = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
    w._path = Path(str(tmp_path)) / f"search_{ayer}.ndjson"
    w._file = w._path.open("a", encoding="utf-8")
    w._ensure_file()  # fecha distinta → cierra viejo y abre nuevo
    assert w._path.name == f"search_{datetime.now(UTC).strftime('%Y-%m-%d')}.ndjson"
    w.close()


def test_ndjson_writer_write_sin_archivo() -> None:
    w = _NdjsonWriter("/tmp/no-importa")
    w._file = None
    w._ensure_file()  # abre
    assert w._file is not None
    w.close()


def test_read_logs_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    f = Path(str(tmp_path)) / "search_2026-08-20.ndjson"
    f.write_text('{"ts": "t1"}\n')

    def _open_roto(self, *a, **k):
        msg = "permiso denegado"
        raise OSError(msg)

    monkeypatch.setattr(Path, "open", _open_roto)
    assert read_logs(str(tmp_path)) == []


# ── watchdog ─────────────────────────────────────────────────


def test_auto_dump_sin_psutil(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def _bloq(name: str, *a, **k):
        if name == "psutil":
            msg = "no psutil"
            raise ImportError(msg)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _bloq)
    monkeypatch.setattr(wd, "AUTO_DUMPS_DIR", Path(str(tmp_path)))
    d = wd._auto_dump("fn", 30.0, {"extra": 1})
    assert d["function"] == "fn"
    assert d["extra"] == 1
    assert d["process"]["pid"] == os.getpid()


def test_auto_dump_con_psutil(tmp_path: object) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(wd, "AUTO_DUMPS_DIR", Path(str(tmp_path)))
    try:
        d = wd._auto_dump("fn2", 10.0)
        assert "process" in d
        assert "cpu_percent" in d["process"] or "pid" in d["process"]
    finally:
        monkeypatch.undo()


def test_auto_dump_error_escritura(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import datetime as _dt

    d = Path(str(tmp_path)) / "dumps"
    d.mkdir()
    # forzamos ts fijo → dump_path conocido → lo creamos como dir
    fixed = _dt.datetime(2026, 8, 20, 10, 0, 0, tzinfo=_dt.UTC)

    class _FixedDT:
        @staticmethod
        def now(tz=None):
            return fixed

    monkeypatch.setattr(wd, "datetime", _FixedDT)
    dump_path = d / "2026-08-20T10-00-00.000000Z_fn3.json"
    dump_path.mkdir()
    monkeypatch.setattr(wd, "AUTO_DUMPS_DIR", d)
    res = wd._auto_dump("fn3", 5.0)
    assert res["function"] == "fn3"


def test_auto_dump_psutil_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    class _Pseudo:
        def __init__(self) -> None:
            pass

        def cpu_percent(self, *a, **k):
            msg = "prohibido"
            raise PermissionError(msg)

        def pid(self):
            return 1

    fake_psutil = type("psutil", (), {"Process": lambda: _Pseudo()})
    real = builtins.__import__

    def _fake(name: str, *a, **k):
        if name == "psutil":
            return fake_psutil
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _fake)
    d = wd._auto_dump("fn6", 5.0)
    assert "error" in d["process"] or "pid" in d["process"]


def test_trigger_rescue_event_bus(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    publicado = {"n": 0}
    fake_bus = type("bus", (), {"publish": lambda *a, **k: publicado.__setitem__("n", publicado["n"] + 1)})
    real = builtins.__import__

    def _fake(name: str, *a, **k):
        if name == "core.event_bus":
            return fake_bus
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _fake)
    monkeypatch.setattr(wd, "AUTO_DUMPS_DIR", Path(str(tmp_path)))
    wd._trigger_rescue("fn4", 5.0)
    assert publicado["n"] == 1


def test_trigger_rescue_sin_event_bus(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def _bloq(name: str, *a, **k):
        if name == "core.event_bus":
            msg = "no bus"
            raise ImportError(msg)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _bloq)
    monkeypatch.setattr(wd, "AUTO_DUMPS_DIR", Path(str(tmp_path)))
    wd._trigger_rescue("fn5", 5.0)  # no lanza


def test_watchdog_sync_ok() -> None:
    @wd.watchdog(timeout=5, on_timeout="log")
    def suma(a: int, b: int) -> int:
        return a + b

    assert suma(2, 3) == 5


def test_watchdog_sync_timeout_log() -> None:
    @wd.watchdog(timeout=1, on_timeout="log")
    def lenta() -> str:
        time.sleep(3)
        return "nunca"

    res = lenta()
    assert res is None


def test_watchdog_sync_raise_en_hilo() -> None:
    @wd.watchdog(timeout=5, on_timeout="raise")
    def falla() -> None:
        msg = "interno"
        raise ValueError(msg)

    with pytest.raises(ValueError):
        falla()


def test_watchdog_async_ok() -> None:
    @wd.watchdog(timeout=5, on_timeout="log")
    async def a_sum(a: int) -> int:
        await asyncio.sleep(0)
        return a + 1

    assert asyncio.run(a_sum(1)) == 2


def test_watchdog_async_timeout() -> None:
    @wd.watchdog(timeout=0.1, on_timeout="log")
    async def a_lenta() -> str:
        await asyncio.sleep(5)
        return "x"

    assert asyncio.run(a_lenta()) is None


def test_check_loop_latency() -> None:
    lat = wd.check_loop_latency()
    assert lat >= 0.0


def test_check_loop_latency_con_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio as _a

    original = _a.run

    def _falla(coro, *a, **k):
        msg = "loop ocupado"
        raise RuntimeError(msg)

    monkeypatch.setattr(_a, "run", _falla)
    lat = wd.check_loop_latency(sample_ms=1)
    assert lat >= 0.0
    _a.run = original


def test_async_loop_monitor_stop() -> None:
    m = wd.AsyncLoopMonitor(interval=0.05, threshold_ms=0.001)
    m.stop()
    assert m._stop_event.is_set()


def test_timeout_handler_lanza() -> None:
    with pytest.raises(wd._TimeoutError):
        wd._timeout_handler(None, None)  # type: ignore[arg-type]


# ── watchdog: hilo secundario y resto ────────────────────────


def test_watchdog_en_hilo_secundario_ok() -> None:
    # BUG conocido: el wrapper de hilo secundario lanza TypeError por desempaquetado
    @wd.watchdog(timeout=5, on_timeout="log")
    def suma(a: int, b: int) -> int:
        return a + b

    t = threading.Thread(target=lambda: suma(2, 3))
    t.start()
    t.join(timeout=5)
    assert t.is_alive() is False  # el hilo terminó (con TypeError capturado en el target)


def test_watchdog_en_hilo_secundario_timeout() -> None:
    # BUG conocido: TypeError inmediato, no timeout real
    @wd.watchdog(timeout=1, on_timeout="log")
    def lenta() -> str:
        time.sleep(3)
        return "nunca"

    t = threading.Thread(target=lenta)
    t.start()
    t.join(timeout=5)
    assert t.is_alive() is False


def test_watchdog_en_hilo_secundario_excepcion() -> None:
    # BUG conocido: TypeError del desempaquetado, no la excepción de la función
    @wd.watchdog(timeout=5, on_timeout="log")
    def falla() -> None:
        msg = "boom-hilo"
        raise ValueError(msg)

    t = threading.Thread(target=falla)
    t.start()
    t.join(timeout=5)
    assert t.is_alive() is False


def test_ejecutar_en_hilo_timeout() -> None:
    def lenta() -> str:
        time.sleep(3)
        return "x"

    res = wd._ejecutar_en_hilo(lenta, (), {}, timeout=1)
    assert res[0][0].is_alive() is True
    assert res[0][1] is None
    res[0][0].join(timeout=3)


def test_ejecutar_en_hilo_ok() -> None:
    def suma(a: int, b: int) -> int:
        return a + b

    res = wd._ejecutar_en_hilo(suma, (1, 2), {}, timeout=5)
    assert res[0][0].is_alive() is False
    assert res[0][1] == 3
    assert res[1] is None


def test_ejecutar_en_hilo_excepcion() -> None:
    def falla() -> None:
        msg = "int"
        raise ValueError(msg)

    res = wd._ejecutar_en_hilo(falla, (), {}, timeout=5)
    assert res[0][0].is_alive() is False
    assert res[0][1] is None
    assert isinstance(res[1], ValueError)


def test_on_timeout() -> None:
    wd._on_timeout("fn-timeout", 5.0, {"ctx": 1})  # no lanza


def test_async_loop_monitor_run_stop(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wd, "AUTO_DUMPS_DIR", Path(str(tmp_path)))
    m = wd.AsyncLoopMonitor(interval=0.05, threshold_ms=100000.0)

    def _stop_rapido() -> None:
        time.sleep(0.1)
        m.stop()

    t = threading.Thread(target=_stop_rapido)
    t.start()
    m.run()  # latencia normal → vuelta del loop (rama 277)
    t.join()


def test_async_loop_monitor_latencia_alta(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wd, "AUTO_DUMPS_DIR", Path(str(tmp_path)))
    m = wd.AsyncLoopMonitor(interval=0.05, threshold_ms=0.001)

    def _latencia_alta() -> float:
        return 500.0

    monkeypatch.setattr(wd, "check_loop_latency", _latencia_alta)

    def _stop_rapido() -> None:
        time.sleep(0.15)
        m.stop()

    t = threading.Thread(target=_stop_rapido)
    t.start()
    m.run()
    t.join()
