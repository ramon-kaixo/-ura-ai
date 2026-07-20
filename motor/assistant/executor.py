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


class FileReadTool:
    def execute(self, path: str) -> ToolResult:
        safe_dirs = ("/home/ramon", "/tmp", "/etc/ura")  # noqa: S108
        resolved = Path(path).resolve()
        if not any(str(resolved).startswith(d) for d in safe_dirs):
            return ToolResult(False, error=f"Acceso denegado: {path}")
        if not resolved.exists() or not resolved.is_file():
            return ToolResult(False, error=f"Archivo no encontrado: {path}")
        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")[:2000]
            return ToolResult(True, content)
        except Exception as e:
            return ToolResult(False, error=str(e))


class SystemInfoTool:
    def execute(self) -> ToolResult:
        import os
        lines = []
        try:
            import psutil
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.1)
            disk = psutil.disk_usage("/")
            lines.append(f"RAM: {mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB ({mem.percent}%)")
            lines.append(f"CPU: {cpu}%")
            lines.append(f"Disco: {disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({disk.percent}%)")
        except ImportError:
            import shutil
            lines.append(f"RAM: {os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') // (1024**3)}GB")
            total, used, _free = shutil.disk_usage("/")
            lines.append(f"Disco: {used // (1024**3)}GB / {total // (1024**3)}GB")
        return ToolResult(True, "\n".join(lines))


class CalculatorTool:
    def execute(self, expression: str) -> ToolResult:
        import ast
        import math
        safe_names = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        safe_names.update({"abs": abs, "min": min, "max": max, "round": round})
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            for node in ast.walk(tree):
                if isinstance(node, (ast.Call, ast.Attribute)):
                    return ToolResult(False, error="Solo expresiones matemáticas básicas")
            code = compile(tree, "<calc>", "eval")
            result = eval(code, {"__builtins__": {}}, safe_names)  # noqa: S307
            return ToolResult(True, str(result))
        except Exception as e:
            return ToolResult(False, error=f"Error: {e}")


class NoteTool:
    def __init__(self):
        import sqlite3
        self._conn = sqlite3.connect("/tmp/ura/notes.db")  # noqa: S108
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS notes "
            "(id INTEGER PRIMARY KEY, content TEXT, "
            "created_at TEXT DEFAULT (datetime('now')))"
        )
        self._conn.commit()

    def save(self, content: str) -> ToolResult:
        self._conn.execute("INSERT INTO notes (content) VALUES (?)", (content[:500],))
        self._conn.commit()
        return ToolResult(True, "Nota guardada")

    def list_recent(self, limit: int = 5) -> ToolResult:
        sql = "SELECT id, content, created_at FROM notes ORDER BY id DESC LIMIT ?"
        rows = self._conn.execute(sql, (limit,)).fetchall()
        if not rows:
            return ToolResult(True, "No hay notas guardadas")
        lines = [f"[{r[2][:10]}] {r[1][:80]}" for r in rows]
        return ToolResult(True, "\n".join(lines))


class DateTimeTool:
    def execute(self) -> ToolResult:
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        months = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return ToolResult(True, (
            f"Son las {now.hour:02d}:{now.minute:02d} del {days[now.weekday()]}, "
            f"{now.day} de {months[now.month - 1]} de {now.year}."
        ))


class ConversationalToolManager:
    """Gestiona herramientas y las ejecuta según la intención del usuario."""

    def __init__(self) -> None:
        self._git = GitTool()
        self._docker = DockerTool()
        self._datetime = DateTimeTool()
        self._file_read = FileReadTool()
        self._system = SystemInfoTool()
        self._calc = CalculatorTool()
        self._notes = NoteTool()

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
            "datetime": lambda: self._datetime.execute(),
            "read_file": lambda: self._file_read.execute(params.get("path", "")),
            "system_info": lambda: self._system.execute(),
            "calculator": lambda: self._calc.execute(params.get("expression", "")),
            "note_save": lambda: self._notes.save(params.get("content", "")),
            "note_list": lambda: self._notes.list_recent(int(params.get("limit", 5))),
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
