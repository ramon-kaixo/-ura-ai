"""Orquestador — Divide planes en tareas y las publica en la cola SQLite.

Recibe un plan global (texto), lo divide en tareas atómicas,
y las publica vía la API REST de la task queue.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

_TASK_QUEUE_URL = "http://localhost:4097"


@dataclass
class PlanPhase:
    id: str
    description: str
    dependencies: list[str]
    priority: int
    estimated_hours: float


class Orchestrator:
    """Divide un plan en tareas y las publica en la cola."""

    def __init__(self, task_queue_url: str = _TASK_QUEUE_URL) -> None:
        self._queue_url = task_queue_url

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """POST a la API de la cola."""
        url = f"{self._queue_url}{path}"
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, method="POST")  # noqa: S310
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                data_resp: dict[str, Any] = json.loads(resp.read())
                return data_resp
        except Exception as e:
            log.error("[ORCHESTRATOR] Error POST %s: %s", path, e)
            raise

    def _parse_plan(self, plan_text: str) -> list[PlanPhase]:
        """Parsea un plan en texto a fases atómicas.

        Formato esperado (markdown):
          ## Fase 1: Nombre
          Descripción de la fase
          - Dependencias: Fase 0
          - Prioridad: 1
          - Horas: 4
        """
        phases = []
        # Split by ## headers
        sections = re.split(r"##\s+(Fase\s+\d+|Phase\s+\d+|Step\s+\d+)", plan_text, flags=re.IGNORECASE)

        current_id = ""
        for _i, section in enumerate(sections):
            header_match = re.match(r"(Fase|Phase|Step)\s+(\d+):?\s*(.*)", section, re.IGNORECASE)
            if header_match:
                current_id = f"phase-{header_match.group(2)}"
                description = header_match.group(3).strip() if header_match.group(3) else ""
                phases.append(
                    PlanPhase(
                        id=current_id,
                        description=description,
                        dependencies=[],
                        priority=0,
                        estimated_hours=2.0,
                    )
                )
            elif current_id and phases:
                # Parse details from section content
                phase = phases[-1]
                lines = section.strip().split("\n")
                desc_lines = []
                for line in lines:
                    dep_match = re.search(r"depend.*?:\s*(.*)", line, re.IGNORECASE)
                    prio_match = re.search(r"prior.*?:\s*(\d+)", line, re.IGNORECASE)
                    hours_match = re.search(r"hora.*?:\s*([\d.]+)", line, re.IGNORECASE)

                    if dep_match:
                        phase.dependencies = [d.strip() for d in dep_match.group(1).split(",")]
                    elif prio_match:
                        phase.priority = int(prio_match.group(1))
                    elif hours_match:
                        phase.estimated_hours = float(hours_match.group(1))
                    elif line.strip():
                        desc_lines.append(line.strip())

                if desc_lines:
                    phase.description = " ".join(desc_lines)

        # If no structured phases found, split by paragraphs
        if not phases:
            paragraphs = [p.strip() for p in plan_text.split("\n\n") if p.strip()]
            for i, para in enumerate(paragraphs):
                phases.append(
                    PlanPhase(
                        id=f"phase-{i + 1}",
                        description=para[:500],
                        dependencies=[f"phase-{i}"] if i > 0 else [],
                        priority=i,
                        estimated_hours=2.0,
                    )
                )

        return phases

    def publish_plan(self, plan_text: str) -> list[dict[str, Any]]:
        """Parsea un plan y publica cada fase como tarea en la cola."""
        phases = self._parse_plan(plan_text)
        tasks = []

        for phase in phases:
            task = self._post(
                "/tasks",
                {
                    "description": phase.description or phase.id,
                    "plan_phase": phase.id,
                    "priority": phase.priority,
                    "context_json": json.dumps(
                        {
                            "dependencies": phase.dependencies,
                            "estimated_hours": phase.estimated_hours,
                        }
                    ),
                },
            )
            tasks.append(task)
            log.info("[ORCHESTRATOR] Tarea publicada: %s (%s)", task["id"], phase.id)

        log.info("[ORCHESTRATOR] %d tareas publicadas desde plan", len(tasks))
        return tasks

    def get_status(self) -> dict[str, Any]:
        """Obtiene el estado actual de la cola."""
        try:
            url = f"{self._queue_url}/stats"
            req = urllib.request.Request(url)  # noqa: S310
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                fases_resp: dict[str, Any] = json.loads(resp.read())
                return fases_resp
        except Exception as e:
            log.error("[ORCHESTRATOR] Error getting status: %s", e)
            return {"error": str(e)}

    def get_pending_tasks(self) -> dict[str, Any]:
        """Obtiene tareas pendientes."""
        try:
            url = f"{self._queue_url}/tasks?status=pending"
            req = urllib.request.Request(url)  # noqa: S310
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                pending_resp: dict[str, Any] = json.loads(resp.read())
                return pending_resp
        except Exception as e:
            log.error("[ORCHESTRATOR] Error getting pending: %s", e)
            return {"tasks": [], "count": 0}
