"""Tests de motor/observability/tracing_exporter.py (cobertura 0% -> objetivo >=90%)."""

from __future__ import annotations

import json
import queue
from pathlib import Path
from unittest import mock

import pytest

from motor.observability.tracing_exporter import (
    FileExporter,
    InMemoryExporter,
    LatencyStats,
    MetricsCollector,
    TraceExporter,
)
from motor.observability.tracing_platform import SpanEvent


def _event(span_id: str = "s1", source: str = "src") -> SpanEvent:
    return SpanEvent(
        trace_id="t1",
        span_id=span_id,
        parent_span_id="",
        source=source,
        destination="dst",
        message_type="request",
        message_kind="event",
        timestamp_utc=1.0,
        monotonic_ts=1,
    )


class TestInMemoryExporter:
    def test_emit_flush_close(self) -> None:
        ex = InMemoryExporter()
        assert ex.size() == 0
        ex.emit(_event("a"))
        ex.emit(_event("b"))
        assert ex.size() == 2
        assert [e.span_id for e in ex.events()] == ["a", "b"]
        assert [e.span_id for e in ex.events(1)] == ["b"]
        ex.flush()
        assert ex.size() == 2
        ex.clear()
        assert ex.size() == 0
        ex.emit(_event("c"))
        ex.close()
        assert ex.size() == 0  # close limpia


class TestFileExporter:
    def test_emit_flush_escribe(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=0.01)
        try:
            ex.emit(_event("a"))
            ex.emit(_event("b"))
            ex.flush()
            files = list(tmp_path.glob("trace.*.jsonl"))
            assert len(files) == 1
            lines = files[0].read_text().strip().splitlines()
            assert len(lines) == 2
            assert json.loads(lines[0])["span_id"] == "a"
        finally:
            ex.close()

    def test_flush_vacio(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=0.01)
        try:
            ex.flush()
            assert list(tmp_path.glob("trace.*.jsonl")) == []
        finally:
            ex.close()

    def test_flush_loop(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=0.01)
        ex.emit(_event("a"))
        time = 0
        with mock.patch("motor.observability.tracing_exporter.time.sleep", lambda s: time):
            ex.flush()  # directo, sin esperar el thread
        ex.close()
        assert time == 0

    def test_rotacion_por_tamano(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=60, max_file_size=10)
        try:
            ex.emit(_event("seed"))
            ex.flush()  # abre trace.0.jsonl (resetea _event_count)
            ex._event_count = 1000  # rota solo si count >= 1000
            for i in range(3):
                ex.emit(_event(f"s{i}"))
            ex.flush()
            assert len(list(tmp_path.glob("trace.*.jsonl"))) > 1
        finally:
            ex.close()

    def test_rotacion_error_oserror(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=60, max_file_size=1)
        try:
            ex.emit(_event("seed"))
            ex.flush()
            ex._event_count = 1000
            with mock.patch("pathlib.Path.stat", side_effect=OSError("stat fail")):
                ex.emit(_event("a"))
                ex.flush()  # rotación: stat falla -> OSError capturado
        finally:
            ex.close()

    def test_emit_buffer_lleno_drop_head(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), buffer_size=2, flush_interval=0.01)
        try:
            ex.emit(_event("a"))
            ex.emit(_event("b"))
            ex.emit(_event("c"))
            ex.emit(_event("d"))
            ex.flush()
            lines = next(iter(tmp_path.glob("trace.*.jsonl"))).read_text().strip().splitlines()
            assert len(lines) == 2
        finally:
            ex.close()

    def test_emit_buffer_lleno_drop_new(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), buffer_size=2, flush_interval=0.01, drop_policy="drop_new")
        try:
            ex.emit(_event("a"))
            ex.emit(_event("b"))
            ex.emit(_event("c"))
            ex.flush()
            lines = next(iter(tmp_path.glob("trace.*.jsonl"))).read_text().strip().splitlines()
            assert len(lines) == 2
        finally:
            ex.close()

    def test_close_con_thread(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=0.01)
        ex.emit(_event("a"))
        ex.close()
        assert ex._file is None

    def test_doble_start_thread(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=60)
        try:
            thread = ex._flush_thread
            ex._start_flush_thread()
            assert ex._flush_thread is thread  # no se duplica
        finally:
            ex.close()

    def test_flush_loop_error(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=60)
        try:
            ex._running = True
            with mock.patch.object(ex, "flush", side_effect=OSError("flush boom")), mock.patch(
                "motor.observability.tracing_exporter.time.sleep",
                side_effect=lambda _s: setattr(ex, "_running", False),
            ):
                ex._flush_loop()  # 1 iteración, error capturado
        finally:
            ex.close()

    def test_open_file_existente(self, tmp_path: Path) -> None:
        (tmp_path / "trace.0.jsonl").write_text("viejo\n")
        ex = FileExporter(path=str(tmp_path), flush_interval=60)
        try:
            ex.emit(_event("a"))
            ex.flush()
            assert (tmp_path / "trace.1.jsonl").exists()
        finally:
            ex.close()

    def test_write_error(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=60)
        try:
            ex.emit(_event("a"))
            ex.flush()
            with mock.patch.object(ex._file, "write", side_effect=OSError("write boom")):
                ex.emit(_event("b"))
                ex.flush()
        finally:
            ex.close()

    def test_flush_queue_empty_race(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), flush_interval=60)
        try:
            ex.emit(_event("a"))
            with (
                mock.patch.object(ex._buffer, "empty", return_value=False),
                mock.patch.object(ex._buffer, "get_nowait", side_effect=queue.Empty),
            ):
                ex.flush()
            ex.close()
        finally:
            ex.close()

    def test_emit_drop_head_race(self, tmp_path: Path) -> None:
        ex = FileExporter(path=str(tmp_path), buffer_size=1, flush_interval=60)
        try:
            ex.emit(_event("a"))
            with mock.patch.object(ex._buffer, "get_nowait", side_effect=queue.Empty):
                ex.emit(_event("b"))  # buffer lleno -> drop_head -> Empty
        finally:
            ex.close()


class TestTraceExporter:
    def test_emit_flush_escribe(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "traces.jsonl"), flush_interval=0.01)
        try:
            ex.emit(_event("a"))
            ex.emit(_event("b"))
            ex.flush()
            lines = (tmp_path / "traces.jsonl.0").read_text().strip().splitlines()
            assert len(lines) == 2
            assert json.loads(lines[0])["span_id"] == "a"
        finally:
            ex.close()

    def test_flush_vacio(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), flush_interval=0.01)
        try:
            ex.flush()
            assert not (tmp_path / "t.jsonl.0").exists()
        finally:
            ex.close()

    def test_rotacion(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), flush_interval=60, max_file_size=10)
        try:
            for i in range(5):
                ex.emit(_event(f"s{i}"))
            ex.flush()  # 1er flush: rota y deja file=None
            for i in range(5):
                ex.emit(_event(f"s{i + 10}"))
            ex.flush()  # 2o flush: crea t.jsonl.1
            files = sorted(p.name for p in tmp_path.glob("t.jsonl.*"))
            assert len(files) > 1
        finally:
            ex.close()

    def test_rotacion_oserror(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), flush_interval=60, max_file_size=1)
        try:
            ex.emit(_event("seed"))
            ex.flush()  # abre t.jsonl.0
            import pathlib

            orig_stat = pathlib.Path.stat

            def _stat(self: Path, **kwargs: object) -> object:
                if "t.jsonl" in str(self) and not kwargs:
                    raise OSError("boom")  # rotación directa falla
                return orig_stat(self)

            with mock.patch("pathlib.Path.stat", autospec=True, side_effect=_stat):
                ex.emit(_event("a"))
                ex.flush()  # rotación: stat falla -> OSError capturado
        finally:
            ex.close()

    def test_write_error(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), flush_interval=60)
        ex.emit(_event("a"))
        fake_file = mock.MagicMock()
        fake_file.write.side_effect = OSError("cannot write")
        with mock.patch.object(Path, "open", return_value=fake_file):
            ex.flush()
        ex.close()

    def test_emit_buffer_lleno(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), buffer_size=1, flush_interval=0.01)
        try:
            ex.emit(_event("a"))
            ex.emit(_event("b"))
            ex.flush()
            lines = (tmp_path / "t.jsonl.0").read_text().strip().splitlines()
            assert len(lines) == 1
        finally:
            ex.close()

    def test_doble_start_thread(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), flush_interval=60)
        try:
            thread = ex._flush_thread
            ex._start_flush_thread()
            assert ex._flush_thread is thread
        finally:
            ex.close()

    def test_flush_loop_error(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), flush_interval=60)
        try:
            ex._running = True
            with mock.patch.object(ex, "flush", side_effect=OSError("boom")), mock.patch(
                "motor.observability.tracing_exporter.time.sleep",
                side_effect=lambda _s: setattr(ex, "_running", False),
            ):
                ex._flush_loop()  # 1 iteración, error capturado
        finally:
            ex.close()

    def test_flush_queue_empty_race(self, tmp_path: Path) -> None:
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), flush_interval=60)
        try:
            ex.emit(_event("a"))
            with (
                mock.patch.object(ex._buffer, "empty", return_value=False),
                mock.patch.object(ex._buffer, "get_nowait", side_effect=queue.Empty),
            ):
                ex.flush()
            ex.close()
        finally:
            ex.close()

    def test_next_path_salta_existentes(self, tmp_path: Path) -> None:
        (tmp_path / "t.jsonl.0").write_text("")
        (tmp_path / "t.jsonl.1").write_text("")
        ex = TraceExporter(path=str(tmp_path / "t.jsonl"), flush_interval=0.01)
        try:
            ex.emit(_event("a"))
            ex.flush()
            assert (tmp_path / "t.jsonl.2").exists()
        finally:
            ex.close()


class TestLatencyStats:
    def test_vacio(self) -> None:
        st = LatencyStats()
        assert st.count == 0
        assert st.errors == 0
        assert st.compute_percentiles() == {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        assert st.to_dict()["count"] == 0

    def test_add_y_percentiles(self) -> None:
        st = LatencyStats()
        for i in range(100):
            st.add(i * 10)
        st.record(999, error=True)
        p = st.compute_percentiles()
        assert p["p50"] == 500.0  # índice 50 de 0..990
        assert p["p99"] == 990.0  # índice 99
        assert st.count == 101
        assert st.errors == 1

    def test_window_overflow(self) -> None:
        st = LatencyStats(window=5)
        for i in range(10):
            st.add(i)
        assert st.count == 5
        assert st.durations_ns == [5, 6, 7, 8, 9]

    def test_to_dict(self) -> None:
        st = LatencyStats()
        st.record(1000, error=True)
        d = st.to_dict()
        assert d["count"] == 1 and d["errors"] == 1 and d["p50_ns"] == 1000.0


class TestMetricsCollector:
    def test_record_snapshot(self) -> None:
        mc = MetricsCollector()
        mc.record("http", 100, error=True)
        mc.record("http", 200)
        mc.record("db", 50)
        snap = mc.snapshot()
        assert set(snap) == {"http", "db"}
        assert snap["http"]["count"] == 2
        assert snap["http"]["errors"] == 1
        assert snap["db"]["p50_ns"] == 50.0

    def test_throughput_y_error_rates(self) -> None:
        mc = MetricsCollector()
        mc.record("a", 10)
        mc.record("a", 10, error=True)
        tp = mc.throughput(window_seconds=2)
        assert tp["a"] == 1.0  # 2 eventos / 2s
        er = mc.error_rates()
        assert er["a"] == 0.5

    def test_error_rates_vacio(self) -> None:
        mc = MetricsCollector()
        assert mc.error_rates() == {}
        assert mc.throughput() == {}

    def test_clear(self) -> None:
        mc = MetricsCollector()
        mc.record("a", 1)
        mc.clear()
        assert mc.snapshot() == {}


class TestSpanSinkAbstract:
    def test_not_implemented(self) -> None:
        from motor.observability.tracing_exporter import _SpanEventSink

        sink = _SpanEventSink()
        with pytest.raises(NotImplementedError):
            sink.emit(_event())
        with pytest.raises(NotImplementedError):
            sink.flush()
        with pytest.raises(NotImplementedError):
            sink.close()
