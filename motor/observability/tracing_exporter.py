"""Trace Exporters — exportadores de eventos de tracing.

Extraido de motor/platform/tracing.py para reducir su tamano.
"""

from __future__ import annotations

import contextlib
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.observability.tracing_platform import SpanEvent

log = logging.getLogger("ura.tracing.exporter")


class _SpanEventSink:
    """Abstract sink for span events. Used for DI in TraceContext."""

    def emit(self, event: SpanEvent) -> None:
        raise NotImplementedError

    def flush(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class InMemoryExporter(_SpanEventSink):
    def __init__(self) -> None:
        self._events: list[SpanEvent] = []
        self._lock = threading.Lock()

    def emit(self, event: SpanEvent) -> None:
        with self._lock:
            self._events.append(event)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        with self._lock:
            self._events.clear()

    def events(self, since: int = 0) -> list[SpanEvent]:
        with self._lock:
            return list(self._events[since:])

    def size(self) -> int:
        with self._lock:
            return len(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class FileExporter(_SpanEventSink):
    MAX_DIR_SIZE = 500 * 1024 * 1024

    def __init__(
        self,
        path: str = "/tmp/ura/traces",
        buffer_size: int = 10000,
        flush_interval: float = 5.0,
        max_file_size: int = 100 * 1024 * 1024,
        drop_policy: str = "drop_head",
    ) -> None:
        self._path = path
        self._max_file_size = max_file_size
        self._flush_interval = flush_interval
        self._drop_policy = drop_policy
        self._buffer: queue.Queue[SpanEvent] = queue.Queue(maxsize=buffer_size)
        self._file_index = 0
        self._event_count = 0
        self._lock = threading.Lock()
        self._flush_thread: threading.Thread | None = None
        self._running = False
        self._file: Any = None
        self._start_flush_thread()

    def _start_flush_thread(self) -> None:
        if self._flush_thread is not None:
            return
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True, name="trace-flusher")
        self._flush_thread.start()

    def _flush_loop(self) -> None:
        while self._running:
            time.sleep(self._flush_interval)
            try:
                self.flush()
            except Exception:
                log.debug("flush error", exc_info=True)

    def _open_file(self) -> None:
        Path(self._path).mkdir(parents=True, exist_ok=True)
        base = Path(self._path) / "trace"
        while Path(f"{base}.{self._file_index}.jsonl").exists():
            self._file_index += 1
        path = f"{base}.{self._file_index}.jsonl"
        self._file = Path(path).open("a")  # noqa: SIM115
        self._event_count = 0

    def emit(self, event: SpanEvent) -> None:
        try:
            self._buffer.put_nowait(event)
        except queue.Full:
            if self._drop_policy == "drop_head":
                try:
                    self._buffer.get_nowait()
                    self._buffer.put_nowait(event)
                except queue.Empty:
                    pass

    def flush(self) -> None:
        events: list[SpanEvent] = []
        while not self._buffer.empty():
            try:
                events.append(self._buffer.get_nowait())
            except queue.Empty:
                break
        if not events:
            return
        with self._lock:
            for event in events:
                self._write_event(event)

    def _write_event(self, event: SpanEvent) -> None:
        if self._file is None:
            self._open_file()
        if self._event_count >= 1000 and self._file is not None:
            try:
                fsize = Path(self._file.name).stat().st_size
                if fsize > self._max_file_size:
                    self._file.close()
                    self._file_index += 1
                    self._open_file()
            except OSError:
                log.debug("flush error during file rotation", exc_info=True)
        try:
            if self._file is not None:
                self._file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
                self._file.flush()
                self._event_count += 1
        except Exception:
            log.debug("write error", exc_info=True)

    def close(self) -> None:
        self._running = False
        if self._flush_thread is not None:
            self._flush_thread.join(timeout=2)
        self.flush()
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None


class TraceExporter(_SpanEventSink):
    """Exporta eventos de tracing a un archivo JSON rotativo."""

    def __init__(
        self,
        path: str = "traces.jsonl",
        buffer_size: int = 10000,
        flush_interval: float = 5.0,
        max_file_size: int = 100 * 1024 * 1024,
    ) -> None:
        self._path = path
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._max_file_size = max_file_size
        self._buffer: queue.Queue[SpanEvent] = queue.Queue(maxsize=buffer_size)
        self._file_index = 0
        self._lock = threading.Lock()
        self._flush_thread: threading.Thread | None = None
        self._running = False
        self._file: Any = None
        self._start_flush_thread()

    def _start_flush_thread(self) -> None:
        if self._flush_thread is not None:
            return
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True, name="trace-flusher")
        self._flush_thread.start()

    def _flush_loop(self) -> None:
        while self._running:
            time.sleep(self._flush_interval)
            try:
                self.flush()
            except Exception:
                log.debug("flush error", exc_info=True)

    def _next_path(self) -> str:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        while Path(f"{self._path}.{self._file_index}").exists():
            self._file_index += 1
        return f"{self._path}.{self._file_index}"

    def emit(self, event: SpanEvent) -> None:
        with contextlib.suppress(queue.Full):
            self._buffer.put_nowait(event)

    def flush(self) -> None:
        events: list[SpanEvent] = []
        while not self._buffer.empty():
            try:
                events.append(self._buffer.get_nowait())
            except queue.Empty:
                break
        if not events:
            return
        with self._lock:
            if self._file is None:
                path = self._next_path()
                self._file = Path(path).open("w")  # noqa: SIM115
                self._event_count = 0
            for event in events:
                try:
                    self._file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
                    self._event_count += 1
                except Exception:
                    log.debug("write error", exc_info=True)
            self._file.flush()
            if self._event_count > 0:
                try:
                    fsize = Path(self._file.name).stat().st_size
                    if fsize > self._max_file_size:
                        self._file.close()
                        self._file = None
                        self._file_index += 1
                        self._event_count = 0
                except OSError:
                    log.debug("flush error during file rotation", exc_info=True)

    def close(self) -> None:
        self._running = False
        if self._flush_thread is not None:
            self._flush_thread.join(timeout=5)
        self.flush()
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None


class LatencyStats:
    def __init__(self, window: int = 1000) -> None:
        self.durations_ns: list[int] = []
        self._error_count: int = 0
        self.window = window

    @property
    def count(self) -> int:
        return len(self.durations_ns)

    @property
    def errors(self) -> int:
        return self._error_count

    def add(self, duration_ns: int) -> None:
        self.durations_ns.append(duration_ns)
        if len(self.durations_ns) > self.window:
            self.durations_ns.pop(0)

    def record(self, duration_ns: int, error: bool = False) -> None:
        self.add(duration_ns)
        if error:
            self._error_count += 1

    def compute_percentiles(self) -> dict[str, float]:
        if not self.durations_ns:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        sorted_durations = sorted(self.durations_ns)
        n = len(sorted_durations)
        return {
            "p50": float(sorted_durations[int(n * 0.50)]),
            "p95": float(sorted_durations[int(n * 0.95)]),
            "p99": float(sorted_durations[int(n * 0.99)]),
        }

    def to_dict(self) -> dict[str, Any]:
        percentiles = self.compute_percentiles()
        return {
            "count": self.count,
            "errors": self._error_count,
            "p50_ns": percentiles["p50"],
            "p95_ns": percentiles["p95"],
            "p99_ns": percentiles["p99"],
        }


class MetricsCollector:
    """Colector de métricas de latencia por subsistema.

    OBS-06: p50/p95/p99 por subsistema.
    Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats: dict[str, LatencyStats] = {}

    def record(
        self,
        subsystem: str,
        duration_ns: int,
        error: bool = False,
    ) -> None:
        with self._lock:
            if subsystem not in self._stats:
                self._stats[subsystem] = LatencyStats()
            self._stats[subsystem].record(duration_ns, error)

    def snapshot(self) -> dict[str, Any]:
        """Compute and return percentiles for all subsystems."""
        with self._lock:
            result: dict[str, Any] = {}
            for subsystem, stats in self._stats.items():
                result[subsystem] = stats.to_dict()
            return result

    def throughput(self, window_seconds: float = 60.0) -> dict[str, float]:
        """Events per second per subsystem (approximate)."""
        with self._lock:
            return {s: st.count / max(window_seconds, 1) for s, st in self._stats.items()}

    def error_rates(self) -> dict[str, float]:
        """Error rate per subsystem."""
        with self._lock:
            return {s: st.errors / max(st.count, 1) for s, st in self._stats.items()}

    def clear(self) -> None:
        with self._lock:
            self._stats.clear()


# ── Global collector ────────────────────────

_global_collector = MetricsCollector()
