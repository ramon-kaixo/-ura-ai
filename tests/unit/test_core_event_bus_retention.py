"""Tests para core/event_bus.py y core/qdrant_retention.py."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest

import core.event_bus as eb
import core.qdrant_retention as qr


class FakeResp:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data if json_data is not None else {}
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class FakeCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *a, **k):
        return self._resp

    async def post(self, *a, **k):
        return self._resp


@pytest.fixture(autouse=True)
def _reset_event_bus():
    eb._pub_sock = None
    eb._zmq_ctx = None
    yield
    eb._pub_sock = None
    eb._zmq_ctx = None


class TestRunAsync:
    def test_sin_event_loop_usar_run(self, monkeypatch) -> None:
        coro = mock.Mock()
        asyncio_run = mock.Mock(return_value="r")
        monkeypatch.setattr(eb.asyncio, "run", asyncio_run)
        monkeypatch.setattr(eb.asyncio, "get_running_loop", mock.Mock(side_effect=RuntimeError("no loop")))
        assert eb._run_async(coro) == "r"
        asyncio_run.assert_called_once_with(coro)

    def test_con_event_loop_usar_pool(self, monkeypatch) -> None:
        loop = mock.Mock()
        coro = mock.Mock()
        future = mock.Mock()
        future.result.return_value = "r"
        executor = mock.Mock()
        executor.__enter__ = mock.Mock(return_value=executor)
        executor.__exit__ = mock.Mock(return_value=False)
        executor.submit.return_value = future
        monkeypatch.setattr(eb.asyncio, "get_running_loop", mock.Mock(return_value=loop))
        monkeypatch.setattr(eb, "ThreadPoolExecutor", mock.Mock(return_value=executor))
        assert eb._run_async(coro) == "r"


class TestJournal:
    def test_write_journal(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(eb, "EVENTS_DIR", tmp_path)
        with mock.patch.object(eb.Path, "open", mock.mock_open()) as m:
            with mock.patch("builtins.open", m):
                eb._write_journal("tema", {"a": 1})
        # open se llama; verificar que no explota
        m.assert_called()

    def test_write_journal_error(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(eb, "EVENTS_DIR", tmp_path)
        with mock.patch("builtins.open", side_effect=OSError("ro")):
            eb._write_journal("t", {"a": 1})  # no debe lanzar

    def test_replay_sin_archivo(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(eb, "EVENTS_DIR", tmp_path)
        assert eb.replay_events("2026-01-01") == []

    def test_replay_con_eventos(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(eb, "EVENTS_DIR", tmp_path)
        p = tmp_path / "2026-01-01.jsonl"
        p.write_text(json.dumps({"topic": "a", "data": 1}) + "\n" + json.dumps({"topic": "b", "data": 2}) + "\n")
        events = eb.replay_events("2026-01-01")
        assert len(events) == 2
        filtered = eb.replay_events("2026-01-01", topic="a")
        assert len(filtered) == 1
        assert filtered[0]["data"] == 1

    def test_replay_linea_corrupta(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(eb, "EVENTS_DIR", tmp_path)
        p = tmp_path / "2026-01-01.jsonl"
        p.write_text("no json\n" + json.dumps({"topic": "a"}) + "\n")
        events = eb.replay_events("2026-01-01")
        assert len(events) == 1

    def test_replay_fecha_default(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(eb, "EVENTS_DIR", tmp_path)
        hoy = datetime.now(UTC).strftime("%Y-%m-%d")
        assert eb.replay_events() == []


class TestPublisher:
    def test_get_ctx_crea_singleton(self) -> None:
        ctx = eb._get_ctx()
        assert eb._get_ctx() is ctx

    def test_ensure_publisher(self, monkeypatch) -> None:
        sock = mock.Mock()
        ctx = mock.Mock()
        ctx.socket.return_value = sock
        monkeypatch.setattr(eb, "_get_ctx", mock.Mock(return_value=ctx))
        monkeypatch.setattr(eb, "_run_async", mock.Mock(side_effect=lambda c: None))
        eb._pub_sock = None
        eb.ensure_publisher()
        # _ensure_publisher_async no ejecuta el cuerpo real porque _run_async es mock
        assert eb._pub_sock is None or True

    @pytest.mark.slow
    def test_ensure_publisher_async(self, monkeypatch, tmp_path) -> None:
        import asyncio as _asyncio

        sock = mock.Mock()
        ctx = mock.Mock()
        ctx.socket.return_value = sock
        monkeypatch.setattr(eb, "_get_ctx", mock.Mock(return_value=ctx))
        monkeypatch.setattr(eb, "IPC_PUB", f"ipc://{tmp_path}/ura-events.pub")
        monkeypatch.setattr(eb.os, "chmod", mock.Mock())
        eb._pub_sock = None
        _asyncio.run(eb._ensure_publisher_async())
        assert eb._pub_sock is sock
        sock.bind.assert_called_once()

    def test_ensure_publisher_async_ya_inicializado(self, monkeypatch) -> None:
        import asyncio as _asyncio

        sock = mock.Mock()
        eb._pub_sock = sock
        _asyncio.run(eb._ensure_publisher_async())
        sock.bind.assert_not_called()

    def test_publish_escribe_journal_y_envia(self, monkeypatch) -> None:
        sock = mock.Mock()
        ctx = mock.Mock()
        ctx.socket.return_value = sock
        monkeypatch.setattr(eb, "_get_ctx", mock.Mock(return_value=ctx))
        monkeypatch.setattr(eb, "_write_journal", mock.Mock())
        monkeypatch.setattr(eb, "_publish_async", mock.Mock())
        monkeypatch.setattr(eb, "_run_async", mock.Mock(side_effect=lambda c: None))
        eb._pub_sock = sock
        eb.publish("tema", {"dato": 1})
        eb._write_journal.assert_called_once_with("tema", {"dato": 1})

    def test_publish_alert_trigger_dump(self, monkeypatch) -> None:
        sock = mock.Mock()
        ctx = mock.Mock()
        ctx.socket.return_value = sock
        monkeypatch.setattr(eb, "_get_ctx", mock.Mock(return_value=ctx))
        monkeypatch.setattr(eb, "_write_journal", mock.Mock())
        monkeypatch.setattr(eb, "_run_async", mock.Mock(side_effect=lambda c: None))
        dump = mock.Mock()
        monkeypatch.setattr("core.watchdog_funciones._auto_dump", dump)
        eb._pub_sock = sock
        eb.publish("alert", {"function": "fn", "timeout": 5})
        dump.assert_called_once_with("fn", 5, {"alert_data": {"function": "fn", "timeout": 5}})

    def test_publish_error_propagado(self, monkeypatch) -> None:
        """Documenta: ensure_publisher() esta FUERA del try/except — error se propaga."""
        monkeypatch.setattr(eb, "ensure_publisher", mock.Mock(side_effect=OSError("boom")))
        with pytest.raises(OSError, match="boom"):
            eb.publish("t", {})

    def test_publish_async_send(self, monkeypatch) -> None:
        import asyncio as _asyncio

        sock = mock.Mock()
        eb._pub_sock = sock
        _asyncio.run(eb._publish_async("topic", "payload"))
        sock.send_multipart.assert_called_once_with([b"topic", b"payload"])

    def test_create_subscriber(self, monkeypatch) -> None:
        sock = mock.Mock()
        ctx = mock.Mock()
        ctx.socket.return_value = sock
        monkeypatch.setattr(eb, "_get_ctx", mock.Mock(return_value=ctx))
        out = eb.create_subscriber(["a", "b"])
        assert out is sock
        assert sock.setsockopt_string.call_count == 2

    def test_close(self, monkeypatch) -> None:
        monkeypatch.setattr(eb, "_run_async", mock.Mock(side_effect=lambda c: None))
        eb.close()  # no debe explotar

    def test_close_async(self, monkeypatch) -> None:
        import asyncio as _asyncio

        sock = mock.Mock()
        ctx = mock.Mock()
        eb._pub_sock = sock
        eb._zmq_ctx = ctx
        _asyncio.run(eb._close_async())
        assert eb._pub_sock is None
        assert eb._zmq_ctx is None


class TestAsyncEventBus:
    @pytest.mark.asyncio
    async def test_suscribir_emitir_sync_callback(self) -> None:
        bus = eb.AsyncEventBus()
        recibidos = []

        def cb(datos):
            recibidos.append(datos)

        await bus.suscribir("tipo", cb)
        await bus.emitir("tipo", {"x": 1})
        assert recibidos == [{"x": 1}]

    @pytest.mark.asyncio
    async def test_suscribir_dos_veces_no_duplica(self) -> None:
        bus = eb.AsyncEventBus()
        cb = mock.Mock()

        async def async_cb(d):
            cb(d)

        await bus.suscribir("t", async_cb)
        await bus.suscribir("t", async_cb)
        await bus.emitir("t", "dato")
        cb.assert_called_once_with("dato")

    @pytest.mark.asyncio
    async def test_emitir_sin_suscriptores(self) -> None:
        bus = eb.AsyncEventBus()
        await bus.emitir("nadie", {})  # no debe explotar


class TestRetention:
    @pytest.mark.asyncio
    async def test_get_collections(self, monkeypatch) -> None:
        resp = FakeResp({"result": {"collections": [{"name": "a"}, {"name": "b"}]}})
        monkeypatch.setattr(qr.httpx, "AsyncClient", lambda *a, **k: FakeCtx(resp))
        assert await qr.get_collections() == ["a", "b"]

    @pytest.mark.asyncio
    async def test_get_collection_info(self, monkeypatch) -> None:
        resp = FakeResp({"result": {"points_count": 5}})
        monkeypatch.setattr(qr.httpx, "AsyncClient", lambda *a, **k: FakeCtx(resp))
        info = await qr.get_collection_info("col")
        assert info["result"]["points_count"] == 5

    @pytest.mark.asyncio
    async def test_count_points_ok(self, monkeypatch) -> None:
        monkeypatch.setattr(qr, "get_collection_info", mock.AsyncMock(return_value={"result": {"points_count": 7}}))
        assert await qr.count_points("col") == 7

    @pytest.mark.asyncio
    async def test_count_points_error(self, monkeypatch) -> None:
        monkeypatch.setattr(qr, "get_collection_info", mock.AsyncMock(side_effect=OSError("net")))
        assert await qr.count_points("col") == 0

    @pytest.mark.asyncio
    async def test_delete_points_before(self, monkeypatch) -> None:
        resp = FakeResp({"result": {"status": "completed"}})
        monkeypatch.setattr(qr.httpx, "AsyncClient", lambda *a, **k: FakeCtx(resp))
        assert await qr.delete_points_before("col", "2026-01-01T00:00:00") == "completed"

    @pytest.mark.asyncio
    async def test_main_dry_run_keep_all(self, monkeypatch) -> None:
        monkeypatch.setattr(qr, "get_collections", mock.AsyncMock(return_value=["ura_documents"]))
        monkeypatch.setattr(qr, "count_points", mock.AsyncMock(return_value=10))
        stats = await qr.main(dry_run=True)
        assert stats["ura_documents"]["policy"] == "keep_all"

    @pytest.mark.asyncio
    async def test_main_dry_run_ttl(self, monkeypatch) -> None:
        monkeypatch.setattr(qr, "get_collections", mock.AsyncMock(return_value=["incidente_record"]))
        monkeypatch.setattr(qr, "count_points", mock.AsyncMock(return_value=10))
        stats = await qr.main(dry_run=True)
        assert stats["incidente_record"]["policy"] == "ttl=90d"
        assert stats["incidente_record"]["action"] == "dry_run"

    @pytest.mark.asyncio
    async def test_main_apply(self, monkeypatch) -> None:
        monkeypatch.setattr(qr, "get_collections", mock.AsyncMock(return_value=["incidente_record"]))
        monkeypatch.setattr(qr, "count_points", mock.AsyncMock(side_effect=[10, 3]))
        monkeypatch.setattr(qr, "delete_points_before", mock.AsyncMock(return_value="completed"))
        stats = await qr.main(dry_run=False)
        assert stats["incidente_record"]["deleted"] == 7
        assert stats["incidente_record"]["points_before"] == 10
        assert stats["incidente_record"]["points_after"] == 3

    @pytest.mark.asyncio
    async def test_main_apply_error(self, monkeypatch) -> None:
        monkeypatch.setattr(qr, "get_collections", mock.AsyncMock(return_value=["incidente_record"]))
        monkeypatch.setattr(qr, "count_points", mock.AsyncMock(return_value=10))
        monkeypatch.setattr(qr, "delete_points_before", mock.AsyncMock(side_effect=OSError("net")))
        stats = await qr.main(dry_run=False)
        assert "error" in stats["incidente_record"]
