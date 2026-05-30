#!/usr/bin/env python3
"""
Task Orchestrator — Modo Enjambre (FASE 4.2)
────────────────────────────────────────────
Divide tareas complejas entre Windsurf (UI/frontend) y
OpenCode (backend/investigación), ejecuta en paralelo,
y consolida resultados.
"""

import concurrent.futures
import time
from dataclasses import dataclass

from core.logging_config import get_logger

logger = get_logger("task_orchestrator", log_dir="./logs")


@dataclass
class Subtask:
    """Una subtarea asignada a un worker."""

    id: str
    description: str
    worker: str  # "opencode", "windsurf", "ollama"
    priority: int = 0


class TaskOrchestrator:
    """
    Orquestador de tareas multi-agente.

    Uso:
        orch = TaskOrchestrator()
        results = orch.execute([
            Subtask("1", "Refactorizar main_final.py", "opencode"),
            Subtask("2", "Rediseñar UI del panel", "windsurf"),
        ])
    """

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="ura-swarm-"
        )

    def execute(self, tasks: list[Subtask], timeout: int = 600) -> dict:
        """
        Ejecuta múltiples subtareas en paralelo.

        Args:
            tasks: Lista de Subtask.
            timeout: Tiempo máximo total en segundos.

        Returns:
            {"ok": bool, "results": [...], "failed": int, "duration_ms": int}
        """
        start = time.time()
        futures = {}
        results = []
        failed = 0

        for task in tasks:
            future = self.executor.submit(self._run_task, task)
            futures[future] = task

        for future in concurrent.futures.as_completed(futures, timeout=timeout):
            task = futures[future]
            try:
                result = future.result(timeout=task.timeout if hasattr(task, "timeout") else 120)
                results.append(
                    {"task_id": task.id, "worker": task.worker, "ok": True, "result": result}
                )
            except Exception as e:
                failed += 1
                results.append(
                    {"task_id": task.id, "worker": task.worker, "ok": False, "error": str(e)}
                )

        duration = int((time.time() - start) * 1000)
        logger.info(f"Swarm: {len(results)} tasks, {failed} failed, {duration}ms")

        return {
            "ok": failed == 0,
            "results": results,
            "failed": failed,
            "duration_ms": duration,
        }

    def _run_task(self, task: Subtask) -> str:
        """Ejecuta una subtarea según el worker asignado."""
        if task.worker == "opencode":
            return self._run_opencode(task)
        elif task.worker == "windsurf":
            return self._run_windsurf(task)
        elif task.worker == "ollama":
            return self._run_ollama(task)
        else:
            return f"Worker desconocido: {task.worker}"

    def _run_opencode(self, task: Subtask) -> str:
        """Ejecuta tarea en OpenCode."""
        try:
            from agents.agente_opencode import get_opencode_agent

            agent = get_opencode_agent()
            result = agent.execute_task(task.description)
            if result["ok"]:
                return result["response"][:2000]
            return f"Error: {result.get('error', 'desconocido')}"
        except Exception as e:
            return f"OpenCode no disponible: {e}"

    def _run_windsurf(self, task: Subtask) -> str:
        """Ejecuta tarea en Windsurf."""
        try:
            from connectors.windsurf_connector import WindsurfConnector

            wf = WindsurfConnector()
            return wf.send_message(task.description) or "Windsurf: sin respuesta"
        except Exception as e:
            return f"Windsurf no disponible: {e}"

    def _run_ollama(self, task: Subtask) -> str:
        """Ejecuta tarea en Ollama local."""
        try:
            import requests

            r = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": task.description,
                    "stream": False,
                    "options": {"max_tokens": 300},
                },
                timeout=60,
            )
            return r.json().get("response", "")[:1000]
        except Exception as e:
            return f"Ollama no disponible: {e}"

    def shutdown(self):
        """Apaga el pool de workers."""
        self.executor.shutdown(wait=False)


# ── Singleton ──────────────────────────────────────────────

_orchestrator: TaskOrchestrator | None = None


def get_task_orchestrator() -> TaskOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TaskOrchestrator()
    return _orchestrator
