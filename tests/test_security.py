"""Tests de seguridad para la plataforma URA.

Cubre:
- Rate limiting en ToolRunner
- Sanitización de payloads en ProtocolValidator
- Límites de recursos por agente
- Detección de manipulaciones
"""

from __future__ import annotations

import pytest

from motor.agents.runner import (
    AgentToolRunner,
    RateLimiter,
    ToolAdapter,
    ToolContract,
    ToolTransientError,
)

# ═══════════════════════════════════════════════════
# Rate limiting
# ═══════════════════════════════════════════════════


class _FastAdapter(ToolAdapter):
    def name(self):
        return "fast"

    def run(self, params):
        return {"ok": True}

    def cancel(self):
        pass


def test_rate_limiter_allows_within_limit() -> None:
    limiter = RateLimiter(max_calls=10, window_seconds=60)
    for _ in range(10):
        limiter.check("test_tool")  # no error


def test_rate_limiter_blocks_excess() -> None:
    limiter = RateLimiter(max_calls=3, window_seconds=60)
    for _ in range(3):
        limiter.check("test_tool")
    with pytest.raises(ToolTransientError, match="Rate limit"):
        limiter.check("test_tool")


def test_rate_limiter_separate_buckets() -> None:
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    limiter.check("tool_a")  # allowed
    limiter.check("tool_b")  # allowed (different bucket)
    with pytest.raises(ToolTransientError):
        limiter.check("tool_a")  # blocked


def test_tool_runner_rate_limit() -> None:
    runner = AgentToolRunner(rate_limiter=RateLimiter(max_calls=2, window_seconds=60))
    runner.register("fast", _FastAdapter(), ToolContract(name="fast", timeout_seconds=5))
    runner.run("fast", {})
    runner.run("fast", {})
    with pytest.raises(ToolTransientError, match="Rate limit"):
        runner.run("fast", {})


# ═══════════════════════════════════════════════════
# Payload sanitization (F28)
# ═══════════════════════════════════════════════════


def test_sanitize_rejects_script_tags() -> None:
    from motor.platform.models import (
        CausationId,
        CorrelationId,
        DeliveryHeader,
        MessageKind,
        RoutingHeader,
        SpanId,
        TraceHeader,
        TraceId,
        VersionHeader,
    )
    from motor.platform.serializer import make_envelope_with_checksum, make_message_id
    from motor.platform.validator import ProtocolValidator

    v = VersionHeader()
    mid = make_message_id("1.0", "1.0", "a", "b", "T", b"<script>alert(1)</script>")
    r = RoutingHeader(message_id=mid, message_type="T", message_kind=MessageKind.COMMAND, source="a", destination="b")
    t = TraceHeader(
        trace_id=TraceId.generate(),
        span_id=SpanId.generate(),
        correlation_id=CorrelationId("c"),
        causation_id=CausationId.root(),
    )
    d = DeliveryHeader()
    env = make_envelope_with_checksum(v, r, t, d, b"<script>alert(1)</script>")

    val = ProtocolValidator()
    with pytest.raises(Exception, match="unsafe_payload"):
        val.validate(env)


def test_sanitize_allows_normal_payload() -> None:
    from motor.platform.validator import ProtocolValidator

    env = _make_env()
    val = ProtocolValidator()
    val.validate(env)  # no error


def _make_env():
    from motor.platform.models import (
        CausationId,
        CorrelationId,
        DeliveryHeader,
        MessageKind,
        RoutingHeader,
        SpanId,
        TraceHeader,
        TraceId,
        VersionHeader,
    )
    from motor.platform.serializer import make_envelope_with_checksum, make_message_id

    v = VersionHeader()
    mid = make_message_id("1.0", "1.0", "a", "b", "T", b'{"ok":true}')
    r = RoutingHeader(message_id=mid, message_type="T", message_kind=MessageKind.COMMAND, source="a", destination="b")
    t = TraceHeader(
        trace_id=TraceId.generate(),
        span_id=SpanId.generate(),
        correlation_id=CorrelationId("c"),
        causation_id=CausationId.root(),
    )
    d = DeliveryHeader()
    return make_envelope_with_checksum(v, r, t, d, b'{"ok":true}')


# ═══════════════════════════════════════════════════
# Resource limits (AgentPolicy)
# ═══════════════════════════════════════════════════


def test_agent_policy_has_security_fields() -> None:
    from motor.agents.models import AgentPolicy

    p = AgentPolicy()
    assert hasattr(p, "max_context_entries")
    assert hasattr(p, "max_memory_bytes")
    assert p.max_context_entries == 1000
    assert p.max_memory_bytes == 50 * 1024 * 1024
