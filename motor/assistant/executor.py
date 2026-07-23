"""ConversationalTools — herramientas reales para el asistente (C2).

Integración con git, docker, shell, búsqueda y más.
Todas las herramientas piden confirmación antes de ejecutar acciones destructivas.
"""

from __future__ import annotations

import ast
import asyncio
import re
import subprocess  # nosec B404
import sys
from datetime import UTC, datetime
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
            r = subprocess.run(  # nosec
                ["git", "-C", self._repo, "status", "--short"], capture_output=True, text=True, timeout=10, check=False
            )
            return ToolResult(True, r.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    def log(self, count: int = 5) -> ToolResult:
        try:
            r = subprocess.run(  # nosec
                ["git", "-C", self._repo, "log", f"-{count}", "--oneline"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return ToolResult(True, r.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    def diff(self) -> ToolResult:
        try:
            r = subprocess.run(  # nosec
                ["git", "-C", self._repo, "diff", "--stat"], capture_output=True, text=True, timeout=10, check=False
            )
            return ToolResult(True, r.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))


class GitBranchTool:
    def execute(self, repo: str = "") -> ToolResult:
        path = repo or str(Path.cwd())
        try:
            res = subprocess.run(  # nosec
                ["git", "-C", path, "branch", "-a"], capture_output=True, text=True, timeout=10, check=False
            )
            return ToolResult(True, res.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))


class GitCommitTool:
    def execute(self, message: str, repo: str = "") -> ToolResult:
        path = repo or str(Path.cwd())
        try:
            res = subprocess.run(  # nosec
                ["git", "-C", path, "commit", "-m", message], capture_output=True, text=True, timeout=10, check=False
            )
            return ToolResult(res.returncode == 0, res.stdout[:2000] or res.stderr[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))


class DockerTool:
    def ps(self) -> ToolResult:
        try:
            r = subprocess.run(  # nosec
                ["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return ToolResult(True, r.stdout[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    def logs(self, container: str, lines: int = 20) -> ToolResult:
        try:
            r = subprocess.run(  # nosec
                ["docker", "logs", "--tail", str(lines), container],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return ToolResult(True, r.stdout[:2000] or r.stderr[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))


class FileReadTool:
    def execute(self, path: str) -> ToolResult:
        safe_dirs = ("/home/ramon", str(Path.home() / ".ura"), "/etc/ura")
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


class _SafeCalculator:
    def __init__(self) -> None:
        import math

        self._env = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        self._env.update({"abs": abs, "min": min, "max": max, "round": round})

    def _eval(self, node: ast.AST) -> float | int:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp):
            val = self._eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +val
            if isinstance(node.op, ast.USub):
                return -val
            raise ValueError("Operador no soportado")
        if isinstance(node, ast.BinOp):
            lhs = self._eval(node.left)
            rhs = self._eval(node.right)
            if isinstance(node.op, ast.Add):
                return lhs + rhs
            if isinstance(node.op, ast.Sub):
                return lhs - rhs
            if isinstance(node.op, ast.Mult):
                return lhs * rhs
            if isinstance(node.op, ast.Div):
                if rhs == 0:
                    raise ZeroDivisionError("Division por cero")
                return lhs / rhs
            if isinstance(node.op, ast.FloorDiv):
                return lhs // rhs
            if isinstance(node.op, ast.Mod):
                return lhs % rhs
            if isinstance(node.op, ast.Pow):
                return lhs**rhs
            raise ValueError("Operador no soportado")
        if isinstance(node, ast.Name):
            name = node.id
            if name in self._env:
                val = self._env[name]
                if isinstance(val, (int, float)):
                    return val
                raise ValueError(f"Funcion no permitida: {name}")
            raise ValueError(f"Nombre no definido: {name}")
        if isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else ""
            if func_name in self._env:
                args = [self._eval(a) for a in node.args]
                val = self._env[func_name]
                if callable(val):
                    result = val(*args)
                    if isinstance(result, (int, float)):
                        return result
                    raise ValueError("Resultado no numerico")
            raise ValueError(f"Llamada no permitida: {func_name}")
        raise ValueError(f"Expresion no soportada: {type(node).__name__}")

    def evaluate(self, expression: str) -> str:
        tree = ast.parse(expression.strip(), mode="eval")
        result = self._eval(tree.body)
        if isinstance(result, float) and result == int(result):
            return str(int(result))
        return str(result)


class CalculatorTool:
    def __init__(self) -> None:
        self._calc = _SafeCalculator()

    def execute(self, expression: str) -> ToolResult:
        if not expression.strip():
            return ToolResult(False, error="No expression")
        try:
            result = self._calc.evaluate(expression)
            return ToolResult(True, result)
        except Exception as e:
            return ToolResult(False, error=f"Error: {e}")


class NoteTool:
    def __init__(self):
        import sqlite3

        from motor.assistant.config import config

        config.ensure_data_dir()
        self._conn = sqlite3.connect(config.db_for("notes"))
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
        now = datetime.now(UTC)
        days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        months = [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ]
        return ToolResult(
            True,
            (
                f"Son las {now.hour:02d}:{now.minute:02d} del {days[now.weekday()]}, "
                f"{now.day} de {months[now.month - 1]} de {now.year}."
            ),
        )


class WeatherTool:
    async def execute(self, location: str = "") -> ToolResult:
        if not location:
            try:
                ip = (await httpx.get("https://ipapi.co/json/", timeout=5)).json()
                location = ip.get("city", "Madrid")
            except Exception:
                location = "Madrid"
        try:
            resp = await httpx.get(
                f"https://wttr.in/{location}?format=%C+%t+%w+%h",
                timeout=10,
            )
            if resp.status_code == 200:
                return ToolResult(True, f"Clima en {location}: {resp.text}")
            return ToolResult(False, error=f"Error clima: {resp.status_code}")
        except Exception as e:
            return ToolResult(False, error=str(e))


class NewsTool:
    async def execute(self) -> ToolResult:
        try:
            resp = await httpx.get(
                "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
                timeout=10,
            )
            if resp.status_code != 200:
                return ToolResult(False, error=f"Error: {resp.status_code}")

            titles = re.findall(r"<title>(.*?)</title>", resp.text)[:5]
            return ToolResult(True, "\n".join(f"• {t}" for t in titles))
        except Exception as e:
            return ToolResult(False, error=str(e))


class ConversationalToolManager:
    """Gestiona herramientas y las ejecuta según la intención del usuario."""

    def __init__(self) -> None:
        self._git = GitTool()
        self._git_branch = GitBranchTool()
        self._git_commit = GitCommitTool()
        self._docker = DockerTool()
        self._datetime = DateTimeTool()
        self._file_read = FileReadTool()
        self._system = SystemInfoTool()
        self._calc = CalculatorTool()
        self._notes = NoteTool()
        self._weather = WeatherTool()
        self._news = NewsTool()
        self._plugins = self._load_plugins()

    def _load_plugins(self) -> dict[str, Any]:
        try:
            from motor.assistant.tool_plugin import discover_plugins

            return discover_plugins()
        except Exception:
            return {}

    async def execute(self, tool_name: str, params: dict[str, Any] | None = None) -> ToolResult:
        params = params or {}
        sync_handlers = {
            "git_status": lambda: self._git.status(),
            "git_log": lambda: self._git.log(int(params.get("count", 5))),
            "git_diff": lambda: self._git.diff(),
            "docker_ps": lambda: self._docker.ps(),
            "docker_logs": lambda: self._docker.logs(params.get("container", ""), int(params.get("lines", 20))),
            "python": lambda: self._python(params.get("code", "")),
            "datetime": lambda: self._datetime.execute(),
            "read_file": lambda: self._file_read.execute(params.get("path", "")),
            "system_info": lambda: self._system.execute(),
            "calculator": lambda: self._calc.execute(params.get("expression", "")),
            "note_save": lambda: self._notes.save(params.get("content", "")),
            "note_list": lambda: self._notes.list_recent(int(params.get("limit", 5))),
            "git_branch": lambda: self._git_branch.execute(params.get("repo", "")),
            "git_commit": lambda: self._git_commit.execute(params.get("message", "commit"), params.get("repo", "")),
        }
        handler = sync_handlers.get(tool_name)
        if handler:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, handler)
        if tool_name == "web_search":
            return await self._web_search(params.get("query", ""))
        if tool_name == "weather":
            return await self._weather.execute(params.get("location", ""))
        if tool_name == "news":
            return await self._news.execute()
        plugin = self._plugins.get(tool_name)
        if plugin:
            return await plugin.execute(params)
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

            for line in resp.text.split("\n"):
                if 'class="result__snippet"' in line:
                    m = re.search(r">(.*?)<", line)
                    if m:
                        texts.append(m.group(1))
            return ToolResult(True, "\n".join(texts[:5]))
        except Exception as e:
            return ToolResult(False, error=str(e))

    def _python(self, code: str) -> ToolResult:
        if not code:
            return ToolResult(False, error="No code")
        try:
            result = subprocess.run(  # nosec
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            return ToolResult(True, (result.stdout or result.stderr)[:2000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    def needs_confirmation(self, tool_name: str, msg: str = "") -> bool:
        dangerous = {"python", "docker_logs", "note_delete", "git_commit", "git_push"}
        if tool_name in dangerous:
            return True
        msg_lower = msg.lower()
        return any(k in msg_lower for k in ("borra", "elimina", "rm ", "drop ", "format", ">"))

    def list_tools(self) -> list[str]:
        return [
            "git_status",
            "git_log",
            "git_diff",
            "docker_ps",
            "docker_logs",
            "web_search",
            "weather",
            "news",
            "python",
            "datetime",
            "calculator",
            "note_save",
        ]
