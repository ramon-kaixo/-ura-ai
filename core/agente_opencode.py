#!/usr/bin/env python3
"""
Agente OpenCode — FASE 4.2
───────────────────────────
Agente de URA que recibe tareas desglosadas del planificador,
las envía a OpenCode (DeepSeek V4 Pro) y reporta el resultado.
"""

import time
from dataclasses import dataclass

from connectors.opencode_connector import (
    get_opencode_connector,
)
from core.logging_config import get_logger

logger = get_logger("opencode_agent", log_dir="./logs")


@dataclass
class AgentTask:
    """Tarea desglosada para el agente OpenCode."""

    id: str
    description: str
    subtask_of: str = ""
    priority: int = 0  # 0=normal, 1=urgente
    category: str = ""  # "code", "review", "plan", "debug"
    context: str = ""


class URAOpenCodeAgent:
    """
    Agente que conecta el planificador de URA con OpenCode.

    Flujo:
    1. El planificador desglosa una tarea compleja en subtareas
    2. Cada subtarea se envía a OpenCode via el connector
    3. Los resultados se consolidan y reportan al planificador
    """

    def __init__(self):
        self.connector = get_opencode_connector()
        self.history: list[dict] = []
        self.max_history = 50

    def execute_task(self, task_description: str, context: str = "") -> dict:
        """
        Ejecuta una tarea simple vía OpenCode.

        Returns:
            {"ok": bool, "response": str, "tokens": int, "time_ms": int}
        """
        start = time.time()
        result = self.connector.assist(task_description, context)

        entry = {
            "task": task_description[:120],
            "ok": result.ok,
            "response": result.response[:500],
            "tokens": result.tokens_used,
            "time_ms": result.duration_ms,
            "timestamp": time.time(),
        }
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

        return {
            "ok": result.ok,
            "response": result.response,
            "tokens": result.tokens_used,
            "time_ms": int((time.time() - start) * 1000),
        }

    def execute_plan(self, tasks: list[AgentTask], consolidate: bool = True) -> dict:
        """
        Ejecuta una lista de subtareas y consolida resultados.

        Args:
            tasks: Lista de AgentTask a ejecutar.
            consolidate: Si True, envía los resultados a OpenCode para síntesis.

        Returns:
            {"ok": bool, "results": [...], "synthesis": str}
        """
        results = []
        for task in tasks:
            logger.info(f"OpenCode agent ejecutando: {task.id}: {task.description[:60]}")
            r = self.execute_task(task.description, task.context)
            results.append({"task_id": task.id, **r})

        synthesis = ""
        if consolidate and len(results) > 1:
            summary_parts = []
            for i, r in enumerate(results):
                status = "✓" if r["ok"] else "✗"
                summary_parts.append(f"{status} Tarea {tasks[i].id}: {r['response'][:200]}")
            summary_text = "\n".join(summary_parts)
            synth = self.connector.assist(
                "Sintetiza los siguientes resultados en un informe conciso:\n\n" + summary_text
            )
            synthesis = synth.response

        return {"ok": all(r["ok"] for r in results), "results": results, "synthesis": synthesis}

    def review_and_suggest(self, file_path: str) -> dict:
        """Revisa un archivo y sugiere mejoras."""
        result = self.connector.review_code(file_path)
        return {
            "file": file_path,
            "ok": result.ok,
            "suggestions": result.response,
        }

    def debug_error(self, error_text: str) -> dict:
        """Analiza un error y sugiere solución."""
        result = self.connector.analyze_error(error_text)
        return {
            "ok": result.ok,
            "analysis": result.response,
        }

    def plan_complex_task(self, description: str) -> dict:
        """Planifica una tarea compleja en subtareas."""
        result = self.connector.plan_task(description)
        return {
            "ok": result.ok,
            "plan": result.response,
        }

    def get_recent_history(self, n: int = 10) -> list[dict]:
        """Devuelve las últimas N entradas del historial."""
        return self.history[-n:]

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para URAOpenCodeAgent.

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos clave

        Returns:
            Dict con {"success": bool, "response": str, "error": str}
        """
        try:
            task = args[0] if args else kwargs.get("task", "")
            context = kwargs.get("context", "")

            if not task:
                return {"success": False, "response": "", "error": "No se proporcionó tarea"}

            result = self.execute_task(task, context)
            return {
                "success": result.get("ok", False),
                "response": result.get("response", ""),
                "error": "" if result.get("ok", False) else "Error en ejecución",
            }
        except Exception as e:
            return {"success": False, "response": "", "error": str(e)}


# ── Singleton ──────────────────────────────────────────────

_agent: URAOpenCodeAgent | None = None


def get_opencode_agent() -> URAOpenCodeAgent:
    global _agent
    if _agent is None:
        _agent = URAOpenCodeAgent()
    return _agent
