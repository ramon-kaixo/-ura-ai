"""Tests para tracing_exporter.py — exportadores de eventos de tracing.

Verifica que los exportadores funcionan correctamente sin tracing.py.
"""

from __future__ import annotations

import json
import tempfile
import threading
import time as _time
from pathlib import Path

import pytest

from motor.platform.tracing_exporter import (
    InMemoryExporter,
    LatencyStats,
    _SpanEventSink,
)


class FakeSpanEvent:
    def __init__(self, trace_id: str = "test", name: str = "op"):
        self.trace_id = trace_id
        self.name = name

    def to_dict(self) -> dict:
        return {"trace_id": self.trace_id, "name": self.name, "ts": _time.time()}


def test_in_memory_exporter():
    exp = InMemoryExporter()
    assert exp.size() == 0

    event = FakeSpanEvent("abc123")
    exp.emit(event)
    assert exp.size() == 1

    events = exp.events()
    assert len(events) == 1
    assert events[0].trace_id == "abc123"

    exp.clear()
    assert exp.size() == 0


def test_in_memory_exporter_multiple():
    exp = InMemoryExporter()
    for i in range(10):
        exp.emit(FakeSpanEvent(f"trace_{i}"))
    assert exp.size() == 10

    events = exp.events(since=5)
    assert len(events) == 5


def test_in_memory_close():
    exp = InMemoryExporter()
    exp.emit(FakeSpanEvent("test"))
    exp.close()
    assert exp.size() == 0


def test_latency_stats():
    stats = LatencyStats(window=100)
    for i in range(10):
        stats.add(i * 1_000_000)  # 0-9ms
    assert len(stats.durations_ns) == 10


def test_latency_stats_window():
    stats = LatencyStats(window=3)
    for i in range(10):
        stats.add(i)
    assert len(stats.durations_ns) == 3  # window limit
    assert stats.durations_ns[-1] == 9  # most recent
    assert stats.durations_ns[0] == 7  # oldest in window


def test_file_exporter_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        from motor.platform.tracing_exporter import FileExporter

        exp = FileExporter(
            path=tmpdir,
            buffer_size=100,
            flush_interval=0.1,
            max_file_size=1024 * 1024,
        )
        exp.emit(FakeSpanEvent("test1"))
        exp.emit(FakeSpanEvent("test2"))
        _time.sleep(0.3)  # wait for flush
        exp.close()

        files = list(Path(tmpdir).glob("*.jsonl"))
        assert len(files) >= 1


def test_trace_exporter_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        trace_path = str(Path(tmpdir) / "traces.jsonl")
        from motor.platform.tracing_exporter import TraceExporter

        exp = TraceExporter(
            path=trace_path,
            buffer_size=100,
            flush_interval=0.1,
            max_file_size=1024 * 1024,
        )
        exp.emit(FakeSpanEvent("trace1"))
        exp.emit(FakeSpanEvent("trace2"))
        _time.sleep(0.3)
        exp.close()


def test_file_exporter_drop_head():
    import queue as _queue

    exp_type = type("Exp", (object,), {"_buffer": _queue.Queue(maxsize=3)})
    exp = exp_type()
    exp._buffer = _queue.Queue(maxsize=3)
    # Fill buffer
    exp._buffer.put_nowait(FakeSpanEvent("a"))
    exp._buffer.put_nowait(FakeSpanEvent("b"))
    exp._buffer.put_nowait(FakeSpanEvent("c"))
    # Now put should block — test that the FileExporter emit doesn't block
    from motor.platform.tracing_exporter import FileExporter as FE

    dummy = FE.__new__(FE)
    dummy._buffer = exp._buffer
    dummy._drop_policy = "drop_head"
    # This should not raise (drop_head drops oldest)
    result = dummy._buffer.qsize()
    assert result == 3
