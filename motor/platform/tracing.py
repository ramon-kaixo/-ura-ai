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
from collections.abc import Generator
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

MAX_EVENTS_PER_TRACE = 10_000  # max span events per trace_id
MAX_TAGS_PER_EVENT = 32  # max k:v pairs per span
MAX_TAG_KEY_LENGTH = 64  # max bytes per tag key
MAX_TAG_VAL_LENGTH = 512  # max bytes per tag value
MAX_TRACE_FILE_BYTES = 1 * 1024**3  # 1 GB max per trace file before rotation
EXPORTER_BUFFER_SIZE = 10000  # max queued events before drop
CPU_BUDGET_FRAC = 0.02  # max fraction of wall time for tracing
LATENCY_BUDGET_NS = 5_000_000  # max 5ms p99 latency for tracing overhead


from motor.platform.tracing_sampler import (
    FORBIDDEN_TAG_EXACT,
    FORBIDDEN_TAG_PREFIXES,
    MAX_TAG_KEY_LENGTH,
    MAX_TAG_VAL_LENGTH,
    MAX_TAGS_PER_EVENT,
    Sampler,
    SamplingStrategy,
    sanitize_tags,
)

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
        msg = "Empty span tree"
        raise SpanTreeError(msg)

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
            color[sid] = GRAY  # noqa: B023
            for s in trace_spans:  # noqa: B023
                if s.parent_span_id == sid:
                    if color[s.span_id] == GRAY:  # noqa: B023
                        return True  # back edge = cycle
                    if color[s.span_id] == WHITE and has_cycle(s.span_id):  # noqa: B023
                        return True
            color[sid] = BLACK  # noqa: B023
            return False

        for s in trace_spans:
            if color[s.span_id] == WHITE and has_cycle(s.span_id):
                msg = f"Trace {trace_id}: cycle detected"
                raise SpanTreeError(msg)

        # Check for spans with non-existent parent (orphans) BEFORE root counting
        missing_parent = [
            s for s in trace_spans if s.parent_span_id not in ("ROOT", "") and s.parent_span_id not in span_map
        ]
        if missing_parent:
            orphan_ids = [s.span_id for s in missing_parent]
            msg = f"Trace {trace_id}: {len(missing_parent)} orphan spans with missing parent: {orphan_ids}"
            raise SpanTreeError(
                msg,
            )

        # Now find roots (spans whose parent is ROOT or "")
        roots: list[SpanEvent] = []
        for s in trace_spans:
            p = s.parent_span_id
            if p in {"ROOT", ""}:
                roots.append(s)

        if len(roots) != 1:
            msg = f"Trace {trace_id}: expected 1 root, got {len(roots)}"
            raise SpanTreeError(msg)

        # Full DFS from root to find all reachable nodes
        def dfs(sid: str) -> None:
            if sid in visited:  # noqa: B023
                return
            visited.add(sid)  # noqa: B023
            for s in trace_spans:  # noqa: B023
                if s.parent_span_id == sid:
                    dfs(s.span_id)

        dfs(roots[0].span_id)

        # Check for unreachable spans (orphans)
        if len(visited) != len(trace_spans):
            unreachable = set(span_map.keys()) - visited
            msg = f"Trace {trace_id}: {len(unreachable)} orphan spans: {unreachable}"
            raise SpanTreeError(msg)


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
    monotonic_ts: int  # monotonic nanoseconds
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
        self._trace_id = (
            trace_id if trace_id is not None else (getattr(TraceContext._local, "trace_id", None) or TraceId.generate())
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
    ) -> Generator[None, None, None]:
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




from motor.platform.tracing_exporter import (
    FileExporter,
    InMemoryExporter,
    LatencyStats,
    MetricsCollector,
    TraceExporter,
    _SpanEventSink,
)

_global_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _global_collector


def record_latency(subsystem: str, duration_ns: int, error: bool = False) -> None:
    _global_collector.record(subsystem, duration_ns, error)
