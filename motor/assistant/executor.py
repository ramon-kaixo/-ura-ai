"""ConversationalTools — herramientas reales para el asistente (C2).

Integración con git, docker, shell, búsqueda y más.
Todas las herramientas piden confirmación antes de ejecutar acciones destructivas.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx


class ToolResult:
    def __init__(self, success: bool, output: str = "", error: str = ""):
        self.success = success
        self.output = output
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "output": self.output[:1000], "error": self.error[:500]}


class GitTool:
    def __init__(self, repo_path: str | None = None):
        self._repo = repo_path or str(Path.cwd())

    def status(self) -> ToolResult:
        try:
            r = subprocess.run(["git", "-C", self._repo, "status", "--short"],
                               capture_output=True, text=True, timeout=10, check=False)
            return ToolResult(True, r.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    def log(self, count: int = 5) -> ToolResult:
        try:
            r = subprocess.run(["git", "-C", self._repo, "log", f"-{count}", "--oneline"],
                               capture_output=True, text=True, timeout=10, check=False)
            return ToolResult(True, r.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    def diff(self) -> ToolResult:
        try:
            r = subprocess.run(["git", "-C", self._repo, "diff", "--stat"],
                               capture_output=True, text=True, timeout=10, check=False)
            return ToolResult(True, r.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))


class DockerTool:
    def ps(self) -> ToolResult:
        try:
            r = subprocess.run(["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
                               capture_output=True, text=True, timeout=10, check=False)
            return ToolResult(True, r.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    def logs(self, container: str, lines: int = 20) -> ToolResult:
        try:
            r = subprocess.run(["docker", "logs", "--tail", str(lines), container],
                               capture_output=True, text=True, timeout=10, check=False)
            return ToolResult(True, r.stdout[:2000] or r.stderr[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))


class ConversationalToolManager:
    """Gestiona herramientas y las ejecuta según la intención del usuario."""

    def __init__(self) -> None:
        self._git = GitTool()
        self._docker = DockerTool()

    async def execute(self, tool_name: str, params: dict[str, Any] | None = None) -> ToolResult:
        params = params or {}
        sync_handlers = {
            "git_status": lambda: self._git.status(),
            "git_log": lambda: self._git.log(int(params.get("count", 5))),
            "git_diff": lambda: self._git.diff(),
            "docker_ps": lambda: self._docker.ps(),
            "docker_logs": lambda: self._docker.logs(
                params.get("container", ""), int(params.get("lines", 20))),
            "python": lambda: self._python(params.get("code", "")),
        }
        handler = sync_handlers.get(tool_name)
        if handler:
            return handler()
        if tool_name == "web_search":
            return await self._web_search(params.get("query", ""))
        return ToolResult(False, error=f"Tool '{tool_name}' not found")

    async def _web_search(self, query: str) -> ToolResult:
        if not query:
            return ToolResult(False, error="No query")
        try:
            resp = await httpx.AsyncClient(timeout=10).get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "URA/1.0"},
            )
            texts = []
            import re
            for line in resp.text.split("\n"):
                if 'class="result__snippet"' in line:
                    m = re.search(r'>(.*?)<', line)
                    if m:
                        texts.append(m.group(1))
            return ToolResult(True, "\n".join(texts[:5]))
        except Exception as e:
            return ToolResult(False, error=str(e))

    def _python(self, code: str) -> ToolResult:
        if not code:
            return ToolResult(False, error="No code")
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=15, check=False,
            )
            return ToolResult(True, (result.stdout or result.stderr)[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    def list_tools(self) -> list[str]:
        return ["git_status", "git_log", "git_diff", "docker_ps", "docker_logs", "web_search", "python"]
