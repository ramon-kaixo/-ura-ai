"""Tests para motor.observability.tracing_platform (TraceContext, span tree)."""
from __future__ import annotations

from unittest import mock

import pytest

from motor.observability.tracing_exporter import MetricsCollector
from motor.observability.tracing_platform import (
    DropPolicy,
    SpanEvent,
    SpanTreeError,
    TraceContext,
    get_metrics_collector,
    record_latency,
    validate_span_tree,
)
from motor.observability.tracing_sampler import Sampler, SamplingStrategy
from motor.platform.models import (
    CausationId,
    CorrelationId,
    DeliveryHeader,
    MessageId,
    MessageKind,
    ProtocolEnvelope,
    RoutingHeader,
    SpanId,
    TraceHeader,
    TraceId,
    VersionHeader,
)


def _span(
    trace_id: str = "t1",
    span_id: str = "s1",
    parent: str = "ROOT",
    source: str = "a",
    destination: str = "b",
    **kwargs,
) -> SpanEvent:
    return SpanEvent(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent,
        source=source,
        destination=destination,
        message_type="test.type",
        message_kind="command",
        timestamp_utc=1.0,
        monotonic_ts=1,
        **kwargs,
    )


class TestDropPolicy:
    def test_values(self):
        assert DropPolicy.DROP_NEWEST == "drop_newest"
        assert DropPolicy.DROP_OLDEST == "drop_oldest"
        assert DropPolicy.BLOCK == "block"


class TestSpanTreeValidation:
    def test_empty_tree_raises(self):
        with pytest.raises(SpanTreeError, match="Empty"):
            validate_span_tree([])

    def test_valid_tree_passes(self):
        spans = [
            _span(span_id="root", parent="ROOT"),
            _span(span_id="child", parent="root"),
        ]
        validate_span_tree(spans)

    def test_cycle_raises(self):
        spans = [
            _span(span_id="root", parent="ROOT"),
            _span(span_id="a", parent="root"),
            _span(span_id="root", parent="a"),
        ]
        with pytest.raises(SpanTreeError, match="cycle"):
            validate_span_tree(spans)

    def test_missing_parent_raises(self):
        spans = [
            _span(span_id="root", parent="ROOT"),
            _span(span_id="child", parent="ghost"),
        ]
        with pytest.raises(SpanTreeError, match="orphan spans"):
            validate_span_tree(spans)

    def test_multiple_roots_raises(self):
        spans = [
            _span(span_id="r1", parent="ROOT"),
            _span(span_id="r2", parent=""),
        ]
        with pytest.raises(SpanTreeError, match="expected 1 root"):
            validate_span_tree(spans)

    def test_unreachable_span_raises(self):
        spans = [
            _span(span_id="root", parent="ROOT"),
            _span(span_id="lone", parent="ghost2"),
        ]
        # missing parent lanza primero, así que creamos un caso con raíz doble
        # que pase el check de parents: todos con padre válido, pero uno aislado
        spans = [
            _span(span_id="root", parent="ROOT"),
            _span(span_id="a", parent="root"),
            _span(span_id="root2", parent="ROOT"),
        ]
        with pytest.raises(SpanTreeError):
            validate_span_tree(spans)

    def test_multiple_traces_validated(self):
        spans = [
            _span(trace_id="t1", span_id="r1", parent="ROOT"),
            _span(trace_id="t1", span_id="c1", parent="r1"),
            _span(trace_id="t2", span_id="r2", parent="ROOT"),
        ]
        validate_span_tree(spans)


class TestSpanEvent:
    def test_to_dict(self):
        event = _span(tags={"a": "b"}, error_code="E1", error_message="msg", duration_ns=5)
        d = event.to_dict()
        assert d["trace_id"] == "t1"
        assert d["tags"] == {"a": "b"}
        assert d["error_code"] == "E1"
        assert d["duration_ns"] == 5


class TestTraceContext:
    def test_defaults_generate_ids(self):
        ctx = TraceContext(source="a", destination="b")
        assert ctx.trace_id
        assert ctx.correlation_id == ctx.trace_id
        assert ctx.causation_id
        assert ctx.span_count == 0
        assert ctx.error_count == 0

    def test_explicit_ids(self):
        trace = TraceId.generate()
        corr = CorrelationId("corr-1")
        caus = CausationId("caus-1")
        parent = SpanId.generate()
        ctx = TraceContext(
            source="a",
            destination="b",
            trace_id=trace,
            correlation_id=corr,
            causation_id=caus,
            parent_span_id=parent,
        )
        assert ctx.trace_id == str(trace)
        assert ctx.correlation_id == "corr-1"
        assert ctx.causation_id == "caus-1"
        header = ctx.make_header()
        assert header.parent_span_id == parent

    def test_thread_local_trace_id_propagation(self):
        trace = TraceId.generate()
        TraceContext._local.trace_id = trace
        try:
            ctx = TraceContext(source="a", destination="b")
            assert ctx.trace_id == str(trace)
        finally:
            del TraceContext._local.trace_id

    def test_set_exporter_and_sampler(self):
        ctx = TraceContext(source="a", destination="b")
        exporter = mock.Mock()
        sampler = Sampler(strategy=SamplingStrategy.ALWAYS)
        ctx.set_exporter(exporter)
        ctx.set_sampler(sampler)
        assert ctx._exporter is exporter
        assert ctx._sampler is sampler

    def test_make_header_generates_span(self):
        ctx = TraceContext(source="a", destination="b")
        header = ctx.make_header()
        assert header.trace_id == ctx._trace_id
        assert header.span_id
        assert header.correlation_id == ctx._correlation_id

    def test_make_header_with_span_id(self):
        ctx = TraceContext(source="a", destination="b")
        span = SpanId.generate()
        header = ctx.make_header(span_id=span)
        assert header.span_id == span

    def test_span_success_emits(self):
        exporter = mock.Mock()
        ctx = TraceContext(source="a", destination="b")
        ctx.set_exporter(exporter)
        with ctx.span(message_type="op", tags={"k": "v"}):
            pass
        assert ctx.span_count == 1
        assert ctx.error_count == 0
        exporter.emit.assert_called_once()
        event = exporter.emit.call_args.args[0]
        assert isinstance(event, SpanEvent)
        assert event.parent_span_id == "ROOT"
        assert event.source == "a"
        assert event.destination == "b"
        assert event.message_type == "op"

    def test_span_exception_records_error_and_reraises(self):
        exporter = mock.Mock()
        ctx = TraceContext(source="a", destination="b")
        ctx.set_exporter(exporter)
        with pytest.raises(RuntimeError, match="boom"), ctx.span(message_type="op"):
            raise RuntimeError("boom")
        assert ctx.error_count == 1
        event = exporter.emit.call_args.args[0]
        assert event.error_code == "RuntimeError"
        assert event.error_message == "boom"

    def test_span_nested_parent(self):
        exporter = mock.Mock()
        ctx = TraceContext(source="a", destination="b")
        ctx.set_exporter(exporter)
        with ctx.span(message_type="outer"), ctx.span(message_type="inner"):
            pass
        assert exporter.emit.call_count == 2
        inner, outer = [c.args[0] for c in exporter.emit.call_args_list]
        assert inner.parent_span_id == outer.span_id

    def test_span_restores_parent_after_exception(self):
        ctx = TraceContext(source="a", destination="b", parent_span_id=SpanId.generate())
        original = ctx._parent_span_id
        with pytest.raises(RuntimeError), ctx.span(message_type="op"):
            raise RuntimeError("x")
        assert ctx._parent_span_id == original

    def test_emit_skipped_by_sampler(self):
        exporter = mock.Mock()
        sampler = Sampler(strategy=SamplingStrategy.NEVER)
        ctx = TraceContext(source="a", destination="b")
        ctx.set_exporter(exporter)
        ctx.set_sampler(sampler)
        with ctx.span(message_type="op"):
            pass
        exporter.emit.assert_not_called()

    def test_emit_records_error_for_adaptive_sampler(self):
        exporter = mock.Mock()
        sampler = mock.Mock()
        sampler.should_sample.return_value = True
        ctx = TraceContext(source="a", destination="b")
        ctx.set_exporter(exporter)
        ctx.set_sampler(sampler)
        with pytest.raises(RuntimeError), ctx.span(message_type="op"):
            raise RuntimeError("x")
        sampler.record_error.assert_called_once_with(True)
        with ctx.span(message_type="ok"):
            pass
        sampler.record_error.assert_called_with(False)

    def test_emit_silent_on_exporter_failure(self):
        exporter = mock.Mock()
        exporter.emit.side_effect = RuntimeError("exporter down")
        ctx = TraceContext(source="a", destination="b")
        ctx.set_exporter(exporter)
        with ctx.span(message_type="op"):
            pass
        assert ctx.span_count == 1

    def test_from_header(self):
        trace = TraceId.generate()
        span = SpanId.generate()
        corr = CorrelationId("corr-x")
        caus = CausationId("caus-x")
        header = TraceHeader(
            trace_id=trace,
            span_id=span,
            parent_span_id=None,
            correlation_id=corr,
            causation_id=caus,
        )
        ctx = TraceContext.from_header(header, source="x", destination="y")
        assert ctx.trace_id == str(trace)
        assert ctx.correlation_id == "corr-x"
        assert ctx.causation_id == "caus-x"
        assert ctx._parent_span_id == span

    def test_to_envelope(self):
        ctx = TraceContext(source="a", destination="b")
        envelope = ProtocolEnvelope(
            version=VersionHeader(),
            routing=RoutingHeader(
                message_id=MessageId.make("1.0", "1.0", "a", "b", "test", b"data"),
                message_type="test",
                message_kind=MessageKind.COMMAND,
                source="a",
                destination="b",
            ),
            trace=TraceHeader(trace_id=TraceId.generate(), span_id=SpanId.generate()),
            delivery=DeliveryHeader(),
            payload=b"data",
            checksum="abc",
            security=None,
        )
        new_env = ctx.to_envelope(envelope, span_id=SpanId.generate())
        assert new_env.trace.trace_id == ctx._trace_id
        assert new_env.payload == b"data"
        assert new_env.checksum == "abc"
        assert new_env.version == envelope.version
        assert new_env.security == envelope.security


class TestGlobalMetrics:
    def test_get_metrics_collector(self):
        assert isinstance(get_metrics_collector(), MetricsCollector)
        assert get_metrics_collector() is get_metrics_collector()

    def test_record_latency(self):
        collector = mock.Mock()
        with mock.patch("motor.observability.tracing_platform._global_collector", collector):
            record_latency("sub", 1000)
            collector.record.assert_called_once_with("sub", 1000, False)
            record_latency("sub", 2000, error=True)
            collector.record.assert_called_with("sub", 2000, True)
