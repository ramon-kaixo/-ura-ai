"""Tool adapters and orchestrator for the conversational assistant."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from motor.agents.base import ToolAdapter
from motor.assistant.models import UserIntent


class GitStatusTool(ToolAdapter):
    def name(self) -> str:
        return "git_status"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = params.get("repo", str(Path.cwd()))
        result = subprocess.run(  # noqa: S603
            ["git", "-C", repo, "status", "--short"],  # noqa: S607
            capture_output=True, text=True, timeout=10, check=False,
        )
        return {"output": result.stdout, "returncode": result.returncode}

    def cancel(self) -> None:
        pass


class GitLogTool(ToolAdapter):
    def name(self) -> str:
        return "git_log"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = params.get("repo", str(Path.cwd()))
        n = int(params.get("count", 5))
        result = subprocess.run(  # noqa: S603
            ["git", "-C", repo, "log", f"-{n}", "--oneline"],  # noqa: S607
            capture_output=True, text=True, timeout=10, check=False,
        )
        return {"output": result.stdout, "returncode": result.returncode}

    def cancel(self) -> None:
        pass


class ShellTool(ToolAdapter):
    def name(self) -> str:
        return "shell"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        cmd = params.get("command", "")
        if not cmd:
            return {"error": "no command provided", "returncode": -1}
        cmd_list = cmd if isinstance(cmd, list) else cmd.split()
        result = subprocess.run(  # noqa: S603
            cmd_list, shell=False, capture_output=True, text=True, timeout=30, check=False,
        )
        return {"output": result.stdout, "returncode": result.returncode}

    def cancel(self) -> None:
        pass


class ToolOrchestrator:
    def __init__(self) -> None:
        self._tools: dict[str, ToolAdapter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for tool in [GitStatusTool(), GitLogTool(), ShellTool()]:
            self._tools[tool.name()] = tool

    def register(self, tool: ToolAdapter) -> None:
        self._tools[tool.name()] = tool

    def select_tool(self, intent: UserIntent, entities: dict[str, str]) -> ToolAdapter | None:
        if intent == UserIntent.COMMAND:
            action, _ = self._parse_action(entities.get("original_text", ""))
            if action in ("status", "log", "git"):
                return self._tools.get("git_status") or self._tools.get("git_log")
            return self._tools.get("shell")
        return None

    def execute(
        self, intent: UserIntent, entities: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool = self.select_tool(intent, entities)
        if tool is None:
            return {"error": "no suitable tool found", "tool": None}
        return tool.run(params or {})

    def _parse_action(self, text: str) -> tuple[str, str]:
        import re
        match = re.match(r"(busca|crea|haz|ejecuta|muestra|lista|navega|status|log|git)\s+(.+)", text.strip().lower())
        if match:
            return match.group(1), match.group(2).strip()
        return "", ""

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
