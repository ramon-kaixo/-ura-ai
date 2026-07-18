"""Distributed Tracing (OBS) — TraceContext, TraceExporter, MetricsCollector.

OBS-01: Single trace_id per operation.
OBS-02: No subsystem creates a new trace_id; only propagates.
OBS-03: Every hop generates a unique span_id.
OBS-04: parent_span_id is mandatory for tree reconstruction.
OBS-05: correlation_id and causation_id never change.
OBS-06: monotonic_ts (time.monotonic_ns) alongside UTC timestamp.
OBS-07: Every error includes span_id.
OBS-08: Tracing never modifies functional behavior.
OBS-09: System works if tracing fails.
OBS-10: Overhead budget <2% CPU, <5% latency.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from motor.platform.models import (
    CausationId,
    CorrelationId,
    ErrorEnvelope,
    ProtocolEnvelope,
    SpanId,
    TraceHeader,
    TraceId,
)

logger = logging.getLogger("ura.tracing")

# ── SpanEvent ──────────────────────────────


@dataclass
class SpanEvent:
    """Un evento de tracing: un salto entre subsistemas.

    OBS-03: each event has a unique span_id.
    OBS-04: parent_span_id links to the previous span.
    """
    trace_id: str
    span_id: str
    parent_span_id: str
    source: str
    destination: str
    message_type: str
    message_kind: str
    timestamp_utc: float  # UTC seconds
    monotonic_ts: int      # monotonic nanoseconds
    duration_ns: int = 0
    error_code: str = ""
    error_message: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "source": self.source,
            "destination": self.destination,
            "message_type": self.message_type,
            "message_kind": self.message_kind,
            "timestamp_utc": self.timestamp_utc,
            "monotonic_ts": self.monotonic_ts,
            "duration_ns": self.duration_ns,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "tags": self.tags,
        }


# ── TraceContext ────────────────────────────


class TraceContext:
    """Contexto de tracing para una operación completa.

    Thread-local: cada hilo tiene su propio contexto.
    OBS-08: no modifica comportamiento funcional.
    OBS-09: todos los fallos son silenciosos.

    Usage:
        ctx = TraceContext(source="f24", destination="f25")
        with ctx.span(message_type="fusion.run", message_kind="command"):
            ...
    """

    _local = threading.local()

    def __init__(
        self,
        source: str,
        destination: str,
        trace_id: TraceId | None = None,
        correlation_id: CorrelationId | None = None,
        causation_id: CausationId | None = None,
        parent_span_id: SpanId | None = None,
    ) -> None:
        self._source = source
        self._destination = destination
        # OBS-01: trace_id is created once at the root
        self._trace_id = trace_id if trace_id is not None else (
            getattr(TraceContext._local, "trace_id", None) or TraceId.generate()
        )
        # OBS-05: correlation_id and causation_id never change
        self._correlation_id = correlation_id or CorrelationId(str(self._trace_id))
        self._causation_id = causation_id or CausationId.root()
        self._parent_span_id = parent_span_id

        # Metrics
        self._span_count = 0
        self._error_count = 0

        self._exporter: TraceExporter | None = None
        self._start_time_ns = 0

    @property
    def trace_id(self) -> str:
        return str(self._trace_id)

    @property
    def correlation_id(self) -> str:
        return str(self._correlation_id)

    @property
    def causation_id(self) -> str:
        return str(self._causation_id)

    @property
    def span_count(self) -> int:
        return self._span_count

    @property
    def error_count(self) -> int:
        return self._error_count

    def set_exporter(self, exporter: TraceExporter) -> None:
        self._exporter = exporter

    def make_header(self, span_id: SpanId | None = None) -> TraceHeader:
        """Build a TraceHeader for a new message.

        OBS-03: generates a new span_id for this hop.
        OBS-04: sets parent_span_id from current.
        """
        new_span = span_id or SpanId.generate()
        now = time.time()
        mono = time.monotonic_ns()
        return TraceHeader(
            trace_id=self._trace_id,
            span_id=new_span,
            parent_span_id=self._parent_span_id,
            correlation_id=self._correlation_id,
            causation_id=self._causation_id,
            timestamp=now,
            monotonic_ts=mono,
        )

    @contextmanager
    def span(
        self,
        message_type: str,
        message_kind: str = "command",
        tags: dict[str, str] | None = None,
    ):
        """Context manager for a single span (hop).

        OBS-08: never modifies behavior — wraps in try/except.
        OBS-09: silent on tracing failures.

        Usage:
            with ctx.span(message_type="memory.append"):
                memory.append(entry)
        """
        span_id = SpanId.generate()
        old_parent = self._parent_span_id
        self._parent_span_id = span_id
        start_ns = time.monotonic_ns()
        start_utc = time.time()
        self._span_count += 1
        error_code = ""
        error_msg = ""

        try:
            yield
        except Exception as e:
            self._error_count += 1
            error_code = type(e).__name__
            error_msg = str(e)
            raise
        finally:
            duration_ns = time.monotonic_ns() - start_ns
            self._parent_span_id = old_parent
            self._emit_span(
                span_id=str(span_id),
                parent=str(old_parent) if old_parent else "ROOT",
                source=self._source,
                destination=self._destination,
                message_type=message_type,
                message_kind=message_kind,
                start_utc=start_utc,
                start_mono=start_ns,
                duration_ns=duration_ns,
                error_code=error_code,
                error_message=error_msg,
                tags=tags or {},
            )

    def _emit_span(
        self,
        span_id: str,
        parent: str,
        source: str,
        destination: str,
        message_type: str,
        message_kind: str,
        start_utc: float,
        start_mono: int,
        duration_ns: int,
        error_code: str,
        error_message: str,
        tags: dict[str, str],
    ) -> None:
        """Emit a span event. OBS-09: silent on failure."""
        try:
            event = SpanEvent(
                trace_id=str(self._trace_id),
                span_id=span_id,
                parent_span_id=parent,
                source=source,
                destination=destination,
                message_type=message_type,
                message_kind=message_kind,
                timestamp_utc=start_utc,
                monotonic_ts=start_mono,
                duration_ns=duration_ns,
                error_code=error_code,
                error_message=error_message,
                tags=tags,
            )
            if self._exporter:
                self._exporter.emit(event)
        except Exception:
            logger.debug("trace emit failed (OBS-09)", exc_info=True)

    @staticmethod
    def from_header(
        header: TraceHeader,
        source: str,
        destination: str,
    ) -> TraceContext:
        """Create a TraceContext from an incoming TraceHeader.

        OBS-02: trace_id is propagated, never created.
        """
        return TraceContext(
            source=source,
            destination=destination,
            trace_id=header.trace_id,
            correlation_id=header.correlation_id,
            causation_id=header.causation_id,
            parent_span_id=header.span_id,
        )

    def to_envelope(
        self,
        envelope: ProtocolEnvelope,
        span_id: SpanId | None = None,
    ) -> ProtocolEnvelope:
        """Replace the trace header in an envelope with current context."""
        new_trace = self.make_header(span_id=span_id)
        return ProtocolEnvelope(
            version=envelope.version,
            routing=envelope.routing,
            trace=new_trace,
            delivery=envelope.delivery,
            payload=envelope.payload,
            checksum=envelope.checksum,
            security=envelope.security,
        )


# ── TraceExporter ───────────────────────────


class TraceExporter:
    """Exporta eventos de tracing a un archivo JSON rotativo.

    OBS-09: fallos silenciosos.
    OBS-10: escritura batch cada N eventos o cada T segundos.
    """

    def __init__(
        self,
        path: str = "traces.jsonl",
        max_events_per_file: int = 10000,
        batch_size: int = 10,
        flush_interval: float = 2.0,
    ) -> None:
        self._path = path
        self._max_events_per_file = max_events_per_file
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._buffer: list[SpanEvent] = []
        self._file_index = 0
        self._event_count = 0
        self._lock = threading.Lock()
        self._closed = False
        self._file: Any = None
        self._last_flush = time.monotonic()

        atexit.register(self.close)

    def _open_file(self) -> None:
        path = self._path
        if self._file_index > 0:
            base, ext = os.path.splitext(self._path)
            path = f"{base}.{self._file_index}{ext}"
        self._file = open(path, "a")
        self._file_event_count = 0

    def emit(self, event: SpanEvent) -> None:
        """Emit a span event. OBS-09: silent on failure."""
        try:
            with self._lock:
                if self._closed:
                    return
                self._buffer.append(event)
                self._event_count += 1
                now = time.monotonic()
                if len(self._buffer) >= self._batch_size or (now - self._last_flush) >= self._flush_interval:
                    self._flush_locked()
        except Exception:
            logger.debug("trace emit failed (OBS-09)", exc_info=True)

    def _flush_locked(self) -> None:
        if not self._buffer:
            self._last_flush = time.monotonic()
            return
        if self._file is None:
            self._open_file()
        for event in self._buffer:
            self._file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
            self._file_event_count += 1
            if self._file_event_count >= self._max_events_per_file:
                self._file.close()
                self._file_index += 1
                self._open_file()
        self._buffer.clear()
        self._last_flush = time.monotonic()

    def flush(self) -> None:
        """Force flush of buffered events."""
        try:
            with self._lock:
                self._flush_locked()
                if self._file:
                    self._file.flush()
        except Exception:
            pass

    def close(self) -> None:
        """Close exporter. Flushes remaining events."""
        try:
            self.flush()
            with self._lock:
                self._closed = True
                if self._file:
                    self._file.close()
                    self._file = None
        except Exception:
            pass

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def path(self) -> str:
        return self._path


# ── MetricsCollector ────────────────────────


@dataclass
class LatencyStats:
    """Latency percentiles for a subsystem."""
    count: int = 0
    errors: int = 0
    total_duration_ns: int = 0
    min_duration_ns: int = 0
    max_duration_ns: int = 0
    durations_ns: list[int] = field(default_factory=list)
    p50_ns: int = 0
    p95_ns: int = 0
    p99_ns: int = 0

    def record(self, duration_ns: int, error: bool = False) -> None:
        self.count += 1
        if error:
            self.errors += 1
        self.total_duration_ns += duration_ns
        if self.count == 1 or duration_ns < self.min_duration_ns:
            self.min_duration_ns = duration_ns
        if self.count == 1 or duration_ns > self.max_duration_ns:
            self.max_duration_ns = duration_ns
        self.durations_ns.append(duration_ns)

    def compute_percentiles(self) -> None:
        if not self.durations_ns:
            return
        sorted_d = sorted(self.durations_ns)
        n = len(sorted_d)
        self.p50_ns = sorted_d[int(n * 0.5)]
        self.p95_ns = sorted_d[int(n * 0.95)]
        self.p99_ns = sorted_d[int(n * 0.99)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "errors": self.errors,
            "total_duration_ms": self.total_duration_ns / 1_000_000,
            "avg_duration_ms": (self.total_duration_ns / max(self.count, 1)) / 1_000_000,
            "min_duration_ms": self.min_duration_ns / 1_000_000,
            "max_duration_ms": self.max_duration_ns / 1_000_000,
            "p50_ms": self.p50_ns / 1_000_000,
            "p95_ms": self.p95_ns / 1_000_000,
            "p99_ms": self.p99_ns / 1_000_000,
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
                stats.compute_percentiles()
                result[subsystem] = stats.to_dict()
            return result

    def throughput(self, window_seconds: float = 60.0) -> dict[str, float]:
        """Events per second per subsystem (approximate)."""
        with self._lock:
            return {
                s: st.count / max(window_seconds, 1)
                for s, st in self._stats.items()
            }

    def error_rates(self) -> dict[str, float]:
        """Error rate per subsystem."""
        with self._lock:
            return {
                s: st.errors / max(st.count, 1)
                for s, st in self._stats.items()
            }

    def clear(self) -> None:
        with self._lock:
            self._stats.clear()


# ── Global collector ────────────────────────

_global_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _global_collector


def record_latency(subsystem: str, duration_ns: int, error: bool = False) -> None:
    _global_collector.record(subsystem, duration_ns, error)
