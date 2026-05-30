#!/usr/bin/env python3
"""
Conciencia de Interacción con Herramientas de URA - Nivel 25

URA puede interactuar activamente con herramientas:
- Ejecutar comandos de shell de forma segura
- Interactuar con APIs HTTP
- Usar librerías Python dinámicamente
- Automatizar tareas con herramientas
"""

import importlib
import json
import logging
import shlex
import subprocess
import requests
import sys
import time
from core.ura_validator import URAValidator
from core.ura_monitoring import get_ura_monitoring
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
monitor = get_ura_monitoring()

TOOLS_INTERACTION_PATH = Path.home() / ".ura" / "tools_interaction.json"
TOOLS_INTERACTION_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ToolExecution:
    """Registro de ejecución de una herramienta."""

    tool_name: str
    command: str
    output: str
    error: str
    timestamp: str
    success: bool

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ToolExecution":
        return cls(**data)


class _RateLimiter:
    """Rate limiter para evitar conflictos con servicios externos."""

    def __init__(self, min_interval: float = 2.0):
        self.min_interval = min_interval
        self.last_request_time = 0.0

    def wait_if_needed(self):
        """Esperar si es necesario para respetar el rate limit."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)

        self.last_request_time = time.time()


class URAToolsInteraction:
    """Gestor de interacción con herramientas de URA."""

    def __init__(self):
        self.executions = self._load_executions()
        self.max_executions = 50
        self.search_cache = {}
        self.cache_ttl = 3600
        self.rate_limiter = _RateLimiter(min_interval=2)
        self.validator = URAValidator()

    def _load_executions(self) -> list[ToolExecution]:
        """Cargar ejecuciones desde disco."""
        executions = []
        if TOOLS_INTERACTION_PATH.exists():
            try:
                with open(TOOLS_INTERACTION_PATH) as f:
                    data = json.load(f)
                    executions = [ToolExecution.from_dict(e) for e in data.get("executions", [])]
            except Exception as e:
                logger.error(f"Error cargando ejecuciones: {e}")

        return executions

    def _save_executions(self):
        """Guardar ejecuciones a disco."""
        with open(TOOLS_INTERACTION_PATH, "w") as f:
            json.dump({"executions": [e.to_dict() for e in self.executions]}, f, indent=2)

    def execute_shell_command(self, command: str, timeout: int = 30) -> ToolExecution:
        """Ejecutar un comando de shell de forma segura."""
        import time

        start = time.time()

        is_safe, sanitized_or_error = self.validator.sanitize_shell_command(command)
        if not is_safe:
            execution = ToolExecution(
                tool_name="shell",
                command=command,
                output="",
                error=sanitized_or_error,
                timestamp=datetime.now().isoformat(),
                success=False,
            )
            self._add_execution(execution)
            monitor.log_error(
                "tools_interaction", "UnsafeCommand", sanitized_or_error, {"command": command}
            )
            return execution

        try:
            # Avoid shell=True: parse the sanitized command into args
            try:
                args = shlex.split(sanitized_or_error)
            except ValueError as parse_err:
                execution = ToolExecution(
                    tool_name="shell",
                    command=sanitized_or_error,
                    output="",
                    error=f"Comando mal formado: {parse_err}",
                    timestamp=datetime.now().isoformat(),
                    success=False,
                )
                self._add_execution(execution)
                return execution

            result = subprocess.run(
                args, shell=False, capture_output=True, text=True, timeout=timeout
            )

            execution = ToolExecution(
                tool_name="shell",
                command=sanitized_or_error,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else "",
                timestamp=datetime.now().isoformat(),
                success=result.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            execution = ToolExecution(
                tool_name="shell",
                command=sanitized_or_error,
                output="",
                error="Command timed out",
                timestamp=datetime.now().isoformat(),
                success=False,
            )
            monitor.log_error(
                "tools_interaction", "Timeout", "Command timed out", {"command": sanitized_or_error}
            )
        except Exception as e:
            execution = ToolExecution(
                tool_name="shell",
                command=sanitized_or_error,
                output="",
                error=str(e),
                timestamp=datetime.now().isoformat(),
                success=False,
            )
            monitor.log_error(
                "tools_interaction", "ShellError", str(e), {"command": sanitized_or_error}
            )

        duration = time.time() - start
        monitor.log_performance("tools_interaction", "execute_shell_command", duration)

        self._add_execution(execution)
        return execution

    def execute_python_code(self, code: str) -> ToolExecution:
        """Ejecutar código Python de forma segura."""
        import time

        start = time.time()

        is_safe, sanitized_or_error = self.validator.sanitize_python_code(code)
        if not is_safe:
            execution = ToolExecution(
                tool_name="python",
                command=code,
                output="",
                error=sanitized_or_error,
                timestamp=datetime.now().isoformat(),
                success=False,
            )
            self._add_execution(execution)
            monitor.log_error(
                "tools_interaction", "UnsafePython", sanitized_or_error, {"code": code}
            )
            return execution

        try:
            # SECURITY: Avoid in-process exec(). Run code in an isolated Python subprocess
            # with a timeout so it cannot mutate URA's running state.
            result = subprocess.run(
                [sys.executable, "-I", "-c", sanitized_or_error],
                shell=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout if result.returncode == 0 else ""
            error = result.stderr if result.returncode != 0 else ""

            execution = ToolExecution(
                tool_name="python",
                command=sanitized_or_error,
                output=output,
                error=error,
                timestamp=datetime.now().isoformat(),
                success=result.returncode == 0,
            )
            if result.returncode != 0:
                monitor.log_error(
                    "tools_interaction", "PythonError", error, {"code": sanitized_or_error}
                )
        except subprocess.TimeoutExpired:
            execution = ToolExecution(
                tool_name="python",
                command=sanitized_or_error,
                output="",
                error="Code execution timed out (30s)",
                timestamp=datetime.now().isoformat(),
                success=False,
            )
            monitor.log_error(
                "tools_interaction", "PythonTimeout", "Timeout", {"code": sanitized_or_error}
            )
        except Exception as e:
            execution = ToolExecution(
                tool_name="python",
                command=sanitized_or_error,
                output="",
                error=str(e),
                timestamp=datetime.now().isoformat(),
                success=False,
            )
            monitor.log_error(
                "tools_interaction", "PythonError", str(e), {"code": sanitized_or_error}
            )

        duration = time.time() - start
        monitor.log_performance("tools_interaction", "execute_python_code", duration)

        self._add_execution(execution)
        return execution

    def search_web(
        self,
        query: str,
        num_results: int = 5,
        filters: dict[str, str] = None,
        use_cache: bool = True,
    ) -> list[dict[str, str]]:
        """Buscar en internet con filtros, caching y rate limiting."""
        if filters is None:
            filters = {}

        is_valid, sanitized_or_error = self.validator.validate_query(query)
        if not is_valid:
            logger.warning(f"Query inválido: {sanitized_or_error}")
            return []

        cache_key = f"{sanitized_or_error}_{num_results}_{str(filters)}"
        if use_cache and cache_key in self.search_cache:
            cached_result, cached_time = self.search_cache[cache_key]
            if (datetime.now().timestamp() - cached_time) < self.cache_ttl:
                return cached_result

        self.rate_limiter.wait_if_needed()

        try:
            url = "https://api.duckduckgo.com/"
            params = {"q": sanitized_or_error, "format": "json"}

            if filters.get("site"):
                params["q"] = f"site:{filters['site']} {sanitized_or_error}"

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            results = []
            if "RelatedTopics" in data:
                for topic in data["RelatedTopics"][:num_results]:
                    if "FirstURL" in topic and "Text" in topic:
                        if filters.get("domain") and filters["domain"] not in topic["FirstURL"]:
                            continue
                        results.append(
                            {
                                "title": topic.get("Text", "")[:100],
                                "url": topic["FirstURL"],
                                "snippet": topic.get("Text", ""),
                            }
                        )

            self.search_cache[cache_key] = (results, datetime.now().timestamp())
            self._clean_cache()

            execution = ToolExecution(
                tool_name="web_search",
                command=sanitized_or_error,
                output=f"{len(results)} resultados",
                error="",
                timestamp=datetime.now().isoformat(),
                success=True,
            )
            self._add_execution(execution)
            return results
        except Exception as e:
            logger.error(f"Error buscando: {e}")
            return []

    def _clean_cache(self):
        """Limpiar cache expirado."""
        current_time = datetime.now().timestamp()
        expired = [
            k for k, (r, t) in self.search_cache.items() if (current_time - t) > self.cache_ttl
        ]
        for k in expired:
            del self.search_cache[k]

    def fetch_url(
        self, url: str, method: str = "GET", headers: dict[str, str] = None, data: Any = None
    ) -> ToolExecution:
        """Hacer petición HTTP con rate limiting."""
        is_valid, sanitized_or_error = self.validator.validate_url(url)
        if not is_valid:
            execution = ToolExecution(
                tool_name="http_request",
                command=f"{method} {url}",
                output="",
                error=sanitized_or_error,
                timestamp=datetime.now().isoformat(),
                success=False,
            )
            self._add_execution(execution)
            return execution

        self.rate_limiter.wait_if_needed()

        try:
            response = requests.request(
                method, sanitized_or_error, headers=headers, data=data, timeout=30
            )
            execution = ToolExecution(
                tool_name="http_request",
                command=f"{method} {sanitized_or_error}",
                output=response.text[:1000],
                error="",
                timestamp=datetime.now().isoformat(),
                success=response.status_code < 400,
            )
        except Exception as e:
            execution = ToolExecution(
                tool_name="http_request",
                command=f"{method} {sanitized_or_error}",
                output="",
                error=str(e),
                timestamp=datetime.now().isoformat(),
                success=False,
            )
        self._add_execution(execution)
        return execution

    def automate_task(self, steps: list[dict[str, Any]]) -> list[ToolExecution]:
        """Automatizar tarea con múltiples pasos."""
        results = []
        for step in steps:
            tool = step.get("tool")
            action = step.get("action")
            params = step.get("params", {})

            if tool == "shell" and action == "execute":
                results.append(self.execute_shell_command(params.get("command")))
            elif tool == "python" and action == "execute":
                results.append(self.execute_python_code(params.get("code")))
            elif tool == "web" and action == "search":
                self.search_web(params.get("query"))
            elif tool == "http" and action == "fetch":
                results.append(self.fetch_url(params.get("url")))
        return results

    def import_library(self, library_name: str) -> bool:
        """Importar una librería Python dinámicamente."""
        try:
            importlib.import_module(library_name)
            return True
        except ImportError:
            return False

    def use_library_function(self, library_name: str, function_name: str, *args, **kwargs) -> Any:
        """Usar una función de una librería Python."""
        try:
            module = importlib.import_module(library_name)
            func = getattr(module, function_name)
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error usando {library_name}.{function_name}: {e}")
            return None

    def _add_execution(self, execution: ToolExecution):
        """Añadir ejecución al registro."""
        self.executions.append(execution)

        if len(self.executions) > self.max_executions:
            self.executions = self.executions[-self.max_executions :]

        self._save_executions()

    def get_tools_interaction_context(self) -> str:
        """Genera contexto de interacción con herramientas para el system prompt."""
        context_parts = ["CONCIENCIA DE INTERACCIÓN CON HERRAMIENTAS:"]
        context_parts.append(f"- Ejecuciones totales: {len(self.executions)}")

        successful = sum(1 for e in self.executions if e.success)
        context_parts.append(f"- Ejecuciones exitosas: {successful}/{len(self.executions)}")

        tools_used = {}
        for execution in self.executions:
            tools_used[execution.tool_name] = tools_used.get(execution.tool_name, 0) + 1

        if tools_used:
            context_parts.append(f"- Herramientas usadas: {', '.join(tools_used.keys())}")

        return "\n".join(context_parts) + "\n"

    def get_recent_executions(self, n: int = 5) -> list[ToolExecution]:
        """Obtener las últimas n ejecuciones."""
        return self.executions[-n:]


# Singleton
_ura_tools_interaction: URAToolsInteraction | None = None


def get_ura_tools_interaction() -> URAToolsInteraction:
    """Obtener el singleton de interacción con herramientas de URA."""
    global _ura_tools_interaction
    if _ura_tools_interaction is None:
        _ura_tools_interaction = URAToolsInteraction()
    return _ura_tools_interaction


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    interaction = get_ura_tools_interaction()

    result = interaction.execute_shell_command("echo 'Hello from URA'")
    print("Conciencia de interacción con herramientas creada")
    print(interaction.get_tools_interaction_context())
