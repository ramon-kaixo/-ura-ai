"""ProtocolEnvelope adapter for ToolRunner (F28-P3).

Wraps any ToolRunner implementation to accept/reply with ProtocolEnvelopes.
Adds trace_id, causation_id, and protocol_version to every tool invocation
without modifying the underlying ToolRunner API.

Addresses critical findings F-01, F-02, F-03, F-04 from F28_PROTOCOL_AUDIT.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from motor.agents.models import ToolRequest, ToolResult

if TYPE_CHECKING:
    from motor.agents.base import ToolRunner
    from motor.platform.models import ProtocolEnvelope


class ProtocolToolRunner:
    """Wraps a ToolRunner with ProtocolEnvelope I/O.

    Usage:
        runner = ProtocolToolRunner(AgentToolRunner())

        # Internal (existing code): unchanged
        result = runner._inner.run("search", {"q": "hello"})

        # Protocol-aware: send/receive envelopes
        request_env = ToolRequest(...).to_envelope()
        response_env = await runner.run_protocol(request_env)
        result = ToolResult.from_envelope(response_env)
    """

    def __init__(self, inner: ToolRunner) -> None:
        self._inner = inner

    def run_protocol(self, envelope: ProtocolEnvelope) -> ProtocolEnvelope:
        """Execute a tool from a ProtocolEnvelope and return a ProtocolEnvelope."""
        request = ToolRequest.from_envelope(envelope)
        raw_result = self._inner.run(request.tool_name, request.params, request.timeout)
        result = ToolResult(
            execution_id=request.execution_id,
            tool_name=request.tool_name,
            success=True,
            data=raw_result,
            duration_ms=0.0,
            attempt=request.attempt,
            protocol_version=request.protocol_version,
        )
        return result.to_envelope()

    def run_raw(self, tool_name: str, params: dict, timeout: int = 30) -> dict:
        """Passthrough to inner ToolRunner.run() — unchanged API."""
        return self._inner.run(tool_name, params, timeout)

    def get_contract(self, tool_name: str) -> Any:
        return self._inner.get_contract(tool_name)

    def cancel(self, tool_name: str) -> None:
        self._inner.cancel(tool_name)
