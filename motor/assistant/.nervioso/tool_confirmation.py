"""ToolConfirmation — pide confirmación antes de ejecutar comandos peligrosos."""
from __future__ import annotations

from dataclasses import dataclass, field

DANGEROUS_TOOLS = frozenset({
    "shell", "git_commit", "git_push", "git_reset", "docker_exec",
    "rm", "delete", "drop", "alter", "truncate",
})

SAFE_TOOLS = frozenset({
    "git_status", "git_log", "git_diff", "web_search", "file_read",
    "list", "show", "search", "status", "help",
})


@dataclass
class ConfirmationRequest:
    tool: str
    params: dict[str, str] = field(default_factory=dict)
    risk_level: str = "low"
    reason: str = ""
    confirmed: bool = False


class ConfirmationManager:
    def __init__(self) -> None:
        self._pending: dict[str, ConfirmationRequest] = {}

    def needs_confirmation(self, tool_name: str, params: dict[str, str] | None = None) -> bool:
        tool_lower = tool_name.lower()
        if tool_lower in SAFE_TOOLS:
            return False
        if tool_lower in DANGEROUS_TOOLS:
            return True
        if params:
            cmd = params.get("command", "").lower()
            if any(k in cmd for k in ("rm ", "drop ", "delete ", "format ", ">")):
                return True
        return False

    def request_confirmation(
        self, request_id: str, tool: str,
        params: dict[str, str] | None = None,
    ) -> ConfirmationRequest:
        tool_lower = tool.lower()
        risk = "high" if tool_lower in DANGEROUS_TOOLS else "medium"
        req = ConfirmationRequest(
            tool=tool,
            params=params or {},
            risk_level=risk,
            reason=f"El comando '{tool}' puede tener efectos destructivos",
        )
        self._pending[request_id] = req
        return req

    def confirm(self, request_id: str) -> ConfirmationRequest | None:
        req = self._pending.get(request_id)
        if req:
            req.confirmed = True
        return req

    def reject(self, request_id: str) -> None:
        self._pending.pop(request_id, None)
