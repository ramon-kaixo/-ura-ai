"""Tests de seguridad para la plataforma URA.

Cubre:
- Rate limiting en ToolRunner
- Límites de recursos por agente
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
# Resource limits (AgentPolicy)
# ═══════════════════════════════════════════════════


def test_agent_policy_has_security_fields() -> None:
    from motor.agents.models import AgentPolicy

    p = AgentPolicy()
    assert hasattr(p, "max_context_entries")
    assert hasattr(p, "max_memory_bytes")
    assert p.max_context_entries == 1000
    assert p.max_memory_bytes == 50 * 1024 * 1024
