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

Sampling (OBS-07): Always, Never, Probabilistic, Adaptive, Priority.
Privacy (OBS-08): tags sanitized — no prompts, docs, keys in traces.
Budget (OBS-10): bounded buffer, max events/trace, max trace size.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import queue
import random
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from motor.platform.models import (
    CausationId,
    CorrelationId,
    ProtocolEnvelope,
    SpanId,
    TraceHeader,
    TraceId,
)

logger = logging.getLogger("ura.tracing")

# ── Budget constants (OBS-10) ───────────────

MAX_EVENTS_PER_TRACE = 10_000         # max span events per trace_id
MAX_TAGS_PER_EVENT = 32                # max k:v pairs per span
MAX_TAG_KEY_LENGTH = 64                # max bytes per tag key
MAX_TAG_VAL_LENGTH = 512               # max bytes per tag value
MAX_TRACE_FILE_BYTES = 1 * 1024**3     # 1 GB max per trace file before rotation
EXPORTER_BUFFER_SIZE = 10000           # max queued events before drop
CPU_BUDGET_FRAC = 0.02                 # max fraction of wall time for tracing
LATENCY_BUDGET_NS = 5_000_000          # max 5ms p99 latency for tracing overhead
FORBIDDEN_TAG_PREFIXES = (              # OBS-08: privacy — prefix match only
    "prompt", "query_", "document_", "key_", "token", "secret",
    "password", "credential", "api_key", "auth_",
)
FORBIDDEN_TAG_EXACT = {                 # whole-word match
    "query", "document", "key", "secret",
}


# ── Sampler (OBS-07) ────────────────────────


class SamplingStrategy(StrEnum):
    ALWAYS = "always"
    NEVER = "never"
    PROBABILISTIC = "probabilistic"
    ADAPTIVE = "adaptive"
    PRIORITY = "priority"


@dataclass
class Sampler:
    """Trace sampling controller.

    Always: sample all traces (default).
    Never: sample no traces.
    Probabilistic: sample with probability p (0.0-1.0).
    Adaptive: increase probability when error rate is high.
    Priority: sample based on trace priority label.
    """

    strategy: SamplingStrategy = SamplingStrategy.ALWAYS
    probability: float = 0.1  # for PROBABILISTIC
    error_rate_window: int = 100  # for ADAPTIVE
    adaptive_min_p: float = 0.05
    adaptive_max_p: float = 1.0

    # Internal state for ADAPTIVE
    _recent_errors: list[bool] = field(default_factory=list)

    def should_sample(self, tags: dict[str, str] | None = None) -> bool:
        if self.strategy == SamplingStrategy.ALWAYS:
            return True
        if self.strategy == SamplingStrategy.NEVER:
            return False
        if self.strategy == SamplingStrategy.PROBABILISTIC:
            return random.random() < self.probability
        if self.strategy == SamplingStrategy.ADAPTIVE:
            if self._recent_errors:
                rate = sum(self._recent_errors) / len(self._recent_errors)
                p = self.adaptive_min_p + (self.adaptive_max_p - self.adaptive_min_p) * rate
                return random.random() < p
            return random.random() < self.adaptive_min_p
        if self.strategy == SamplingStrategy.PRIORITY:
            tags = tags or {}
            priority = tags.get("priority", "normal")
            return priority in ("critical", "high")
        return True

    def record_error(self, was_error: bool) -> None:
        self._recent_errors.append(was_error)
        if len(self._recent_errors) > self.error_rate_window:
            self._recent_errors.pop(0)


# ── Privacy: tag sanitization (OBS-08) ──────


def sanitize_tags(tags: dict[str, str]) -> dict[str, str]:
    """Remove or truncate sensitive tag values.

    OBS-08: no prompts, documents, keys, tokens in traces.
    Uses prefix and exact matching to avoid false positives (e.g., "safe_key").
    """
    result: dict[str, str] = {}
    for k, v in tags.items():
        k_lower = k.lower().strip()
        # Check exact match
        if k_lower in FORBIDDEN_TAG_EXACT:
            continue
        # Check prefix match
        if any(k_lower.startswith(p) for p in FORBIDDEN_TAG_PREFIXES):
            continue
        # Truncate key
        k_clean = k[:MAX_TAG_KEY_LENGTH]
        # Truncate value
        v_clean = v[:MAX_TAG_VAL_LENGTH]
        result[k_clean] = v_clean
        if len(result) >= MAX_TAGS_PER_EVENT:
            break
    return result


# ── DropPolicy (OBS-04 backpressure) ────────


class DropPolicy(StrEnum):
    """Backpressure strategy when the TraceExporter buffer is full.

    DROP_NEWEST: discard the incoming event (default, lowest overhead).
    DROP_OLDEST: drain the oldest event from the queue to make room.
    BLOCK: block the caller until space frees up (may impact throughput).
    """
    DROP_NEWEST = "drop_newest"
    DROP_OLDEST = "drop_oldest"
    BLOCK = "block"


# ── SpanTreeValidator (OBS-02/04) ────────────


class SpanTreeError(Exception):
    """Error in span tree structure."""
    pass


def validate_span_tree(spans: list[SpanEvent]) -> None:
    """Validate a span tree.

    Checks:
    - No cycles (OBS-02)
    - No multiple roots for the same trace (OBS-02)
    - No orphan spans (OBS-04)
    - No missing parents (OBS-04)
    - All span_ids unique per trace

    Raises SpanTreeError if any check fails.
    """
    if not spans:
        raise SpanTreeError("Empty span tree")

    by_trace: dict[str, list[SpanEvent]] = {}
    for s in spans:
        by_trace.setdefault(s.trace_id, []).append(s)

    for trace_id, trace_spans in by_trace.items():
        span_map = {s.span_id: s for s in trace_spans}
        visited: set[str] = set()
        in_degree: dict[str, int] = {}
        for s in trace_spans:
            p = s.parent_span_id
            if p not in ("ROOT", "") and p in span_map:
                in_degree[p] = in_degree.get(p, 0) + 1

        # First: detect cycles via DFS with coloring
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {s.span_id: WHITE for s in trace_spans}

        def has_cycle(sid: str) -> bool:
            color[sid] = GRAY
            for s in trace_spans:
                if s.parent_span_id == sid:
                    if color[s.span_id] == GRAY:
                        return True  # back edge = cycle
                    if color[s.span_id] == WHITE and has_cycle(s.span_id):
                        return True
            color[sid] = BLACK
            return False

        for s in trace_spans:
            if color[s.span_id] == WHITE:
                if has_cycle(s.span_id):
                    raise SpanTreeError(f"Trace {trace_id}: cycle detected")

        # Check for spans with non-existent parent (orphans) BEFORE root counting
        missing_parent = [
            s for s in trace_spans
            if s.parent_span_id not in ("ROOT", "")
            and s.parent_span_id not in span_map
        ]
        if missing_parent:
            orphan_ids = [s.span_id for s in missing_parent]
            raise SpanTreeError(
                f"Trace {trace_id}: {len(missing_parent)} orphan spans "
                f"with missing parent: {orphan_ids}"
            )

        # Now find roots (spans whose parent is ROOT or "")
        roots: list[SpanEvent] = []
        for s in trace_spans:
            p = s.parent_span_id
            if p == "ROOT" or p == "":
                roots.append(s)

        if len(roots) != 1:
            raise SpanTreeError(
                f"Trace {trace_id}: expected 1 root, got {len(roots)}"
            )

        # Full DFS from root to find all reachable nodes
        def dfs(sid: str) -> None:
            if sid in visited:
                return
            visited.add(sid)
            for s in trace_spans:
                if s.parent_span_id == sid:
                    dfs(s.span_id)

        dfs(roots[0].span_id)

        # Check for unreachable spans (orphans)
        if len(visited) != len(trace_spans):
            unreachable = set(span_map.keys()) - visited
            raise SpanTreeError(
                f"Trace {trace_id}: {len(unreachable)} orphan spans: {unreachable}"
            )

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

        self._exporter: _SpanEventSink | None = None
        self._sampler: Sampler | None = None
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

    def set_exporter(self, exporter: _SpanEventSink) -> None:
        self._exporter = exporter

    def set_sampler(self, sampler: Sampler) -> None:
        self._sampler = sampler

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
        """Emit a span event. OBS-09: silent on failure.

        Applies sampler (OBS-07) and privacy sanitization (OBS-08).
        """
        try:
            # Privacy: sanitize tags before emission (OBS-08)
            clean_tags = sanitize_tags(tags)

            # Sampling check (OBS-07)
            if self._sampler and not self._sampler.should_sample(clean_tags):
                return

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
                tags=clean_tags,
            )
            if self._exporter:
                self._exporter.emit(event)
                # Track error for adaptive sampler
                if self._sampler and error_code:
                    self._sampler.record_error(True)
                elif self._sampler:
                    self._sampler.record_error(False)
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


# ── Abstract Exporter ──────────────────────


class _SpanEventSink:
    """Abstract sink for span events. Used for DI in TraceContext."""
    def emit(self, event: SpanEvent) -> None:
        raise NotImplementedError

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


# ── InMemoryExporter (for testing, OBS-05 roundtrip) ─


class InMemoryExporter(_SpanEventSink):
    """Captures all events in memory. Used for roundtrip testing (OBS-05)."""

    def __init__(self) -> None:
        self.events: list[SpanEvent] = []
        self._lock = threading.Lock()

    def emit(self, event: SpanEvent) -> None:
        with self._lock:
            self.events.append(event)

    def clear(self) -> None:
        with self._lock:
            self.events.clear()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self.events)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


# ── TraceExporter ───────────────────────────


class TraceExporter(_SpanEventSink):
    """Exporta eventos de tracing a un archivo JSON rotativo.

    OBS-09: fallos silenciosos — nunca bloquea la aplicación.
    OBS-10: bounded queue + background flush thread.
    Backpressure (OBS-04): bounded queue with non-blocking put.
    Privacy (OBS-08): tags sanitized before write.
    Budget (OBS-10): max file size 1 GB, rotation, bounded buffer.
    """

    def __init__(
        self,
        path: str = "traces.jsonl",
        max_events_per_file: int = 10000,
        batch_size: int = 10,
        flush_interval: float = 2.0,
        buffer_size: int = 10000,
        drop_policy: DropPolicy = DropPolicy.DROP_NEWEST,
    ) -> None:
        self._path = path
        self._max_events_per_file = max_events_per_file
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._drop_policy = drop_policy
        self._buffer: queue.Queue = queue.Queue(maxsize=buffer_size)
        self._file_index = 0
        self._event_count = 0
        self._dropped_count = 0
        self._closed = False
        self._file: Any = None
        self._last_flush = time.monotonic()
        self._lock = threading.Lock()
        self._flush_buf: list[SpanEvent] = []

        # Background flush thread (daemon: no bloquea shutdown)
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        atexit.register(self.close)

    def _open_file(self) -> None:
        path = self._path
        if self._file_index > 0:
            base, ext = os.path.splitext(self._path)
            path = f"{base}.{self._file_index}{ext}"
        try:
            self._file = open(path, "a")
            self._file_event_count = 0
        except OSError:
            self._file = None  # OBS-09: silent on file errors

    def emit(self, event: SpanEvent) -> None:
        """Emit a span event. OBS-09: silent on failure.

        Backpressure strategy controlled by drop_policy:
        - DROP_NEWEST: discard incoming event (default, O(1))
        - DROP_OLDEST: drain oldest from queue to make room (O(1))
        - BLOCK: block caller until space frees up (max 5s timeout)

        Metrics via dropped_count / event_count properties.
        """
        with self._lock:
            self._event_count += 1

        try:
            if self._drop_policy == DropPolicy.BLOCK:
                self._buffer.put(event, timeout=5.0)
                return
            self._buffer.put_nowait(event)
            return
        except queue.Full:
            pass
        except Exception:
            logger.debug("trace emit failed (OBS-09)", exc_info=True)
            return

        # Buffer is full — apply drop policy
        if self._drop_policy == DropPolicy.DROP_OLDEST:
            try:
                self._buffer.get_nowait()
                self._buffer.put_nowait(event)
                return
            except (queue.Empty, queue.Full):
                pass

        with self._lock:
            self._dropped_count += 1

    def _flush_loop(self) -> None:
        """Background thread: flush buffer periodically. OBS-09: silent."""
        while not self._closed:
            try:
                event = self._buffer.get(timeout=self._flush_interval)
                self._flush_buf.append(event)
                # Batch flush: drain as many as possible
                while len(self._flush_buf) < self._batch_size:
                    try:
                        self._flush_buf.append(self._buffer.get_nowait())
                    except queue.Empty:
                        break
                self._write_batch()
            except queue.Empty:
                # Timeout: flush what we have
                if self._flush_buf:
                    self._write_batch()
            except Exception:
                logger.debug("flush loop error (OBS-09)", exc_info=True)

    def _write_batch(self) -> None:
        if not self._flush_buf:
            return
        if self._file is None:
            self._open_file()
        if self._file is None:
            self._flush_buf.clear()
            return  # OBS-09: silent if file can't be opened

        for event in self._flush_buf:
            # Privacy: sanitize tags before write (OBS-08)
            d = event.to_dict()
            d["tags"] = sanitize_tags(d.get("tags", {}))
            self._file.write(json.dumps(d, ensure_ascii=False) + "\n")
            self._file_event_count += 1
            self._file.flush()  # Durability: flush every event
            # Rotate if file too large (OBS-10 budget)
            if self._file_event_count >= self._max_events_per_file:
                self._file.close()
                self._file_index += 1
                self._open_file()
        self._flush_buf.clear()

    def flush(self) -> None:
        """Force flush of buffered events."""
        try:
            # Drain queue
            while True:
                try:
                    self._flush_buf.append(self._buffer.get_nowait())
                except queue.Empty:
                    break
            self._write_batch()
            if self._file:
                self._file.flush()
        except Exception:
            logger.exception("Error haciendo flush del TraceExporter")

    def close(self) -> None:
        """Close exporter. Flushes remaining events."""
        try:
            self._closed = True
            self.flush()
            with self._lock:
                if self._file:
                    self._file.close()
                    self._file = None
        except Exception:
            logger.exception("Error cerrando TraceExporter")

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    @property
    def path(self) -> str:
        return self._path

    @property
    def drop_policy(self) -> str:
        return self._drop_policy.value

    @property
    def buffer_size(self) -> int:
        return self._buffer.maxsize

    @property
    def buffer_used(self) -> int:
        return self._buffer.qsize()

    def metrics_dict(self) -> dict[str, int | str]:
        """Prometheus-friendly metrics snapshot."""
        with self._lock:
            return {
                "trace_exporter_emitted_total": self._event_count,
                "trace_exporter_dropped_total": self._dropped_count,
                "trace_exporter_buffer_size": self._buffer.maxsize,
                "trace_exporter_buffer_used": self._buffer.qsize(),
                "trace_exporter_drop_policy": self._drop_policy.value,
            }


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
