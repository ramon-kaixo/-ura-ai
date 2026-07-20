"""Goal Manager v3.1 — cola de objetivos, prioridades dinámicas, dependencias.

NO conoce Planner, Executor ni Evaluator.
Se comunica solo a través del PipelineEngine y el ExecutionLedger.
Persiste objetivos en .nervioso/goals/ para reanudación tras reinicio.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class GoalManager:
    """Gestión de objetivos autónomos con cola, prioridades y dependencias."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._goals_dir = engine.config.nervioso / "goals"
        self._goals_dir.mkdir(parents=True, exist_ok=True)
        self._goals: dict[str, dict[str, Any]] = {}
        self._load_persisted()

    # ── Persistencia ──

    def _goal_path(self, goal_id: str) -> Path:
        return self._goals_dir / f"{goal_id}.json"

    def _save_goal(self, goal: dict) -> None:
        self._goal_path(goal["goal_id"]).write_text(json.dumps(goal, indent=2, ensure_ascii=False))

    def _load_persisted(self) -> None:
        for f in self._goals_dir.glob("*.json"):
            try:
                g = json.loads(f.read_text(encoding="utf-8"))
                self._goals[g["goal_id"]] = g
            except (json.JSONDecodeError, OSError, KeyError):
                f.unlink(missing_ok=True)

    # ── Creación ──

    def create(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        budget: dict | None = None,
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        goal = {
            "goal_id": uuid.uuid4().hex[:12],
            "title": title,
            "description": description,
            "priority": priority,
            "priority_order": PRIORITY_ORDER.get(priority, 99),
            "status": "pending",
            "budget": budget or {"time_max_s": 3600, "changes_max": 50, "cost_max": 10},
            "dependencies": dependencies or [],
            "tags": tags or [],
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "result": None,
            "progress": "",
        }
        self._goals[goal["goal_id"]] = goal
        self._save_goal(goal)
        self._engine.ledger.set_goal(goal)
        self._engine.ledger.add_decision(
            "goal_created",
            {"goal_id": goal["goal_id"], "title": title, "priority": priority},
        )
        return goal

    # ── Consulta ──

    def get(self, goal_id: str) -> dict[str, Any] | None:
        return self._goals.get(goal_id)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._goals.values())

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        return [g for g in self._goals.values() if g["status"] == status]

    # ── Cola priorizada ──

    def next_ready(self) -> dict[str, Any] | None:
        """Retorna el siguiente objetivo listo para ejecutar según prioridad.

        Solo considera objetivos pending cuyas dependencias estén cumplidas.
        """
        ready = [
            g for g in self._goals.values()
            if g["status"] == "pending"
            and all(
                self._goals.get(dep, {}).get("status") == "completed"
                for dep in g.get("dependencies", [])
            )
        ]
        if not ready:
            return None
        ready.sort(key=lambda g: (g.get("priority_order", 99), g.get("created_at", "")))
        return ready[0]

    def queue(self) -> list[dict[str, Any]]:
        """Retorna la cola ordenada por prioridad."""
        pending = self.list_by_status("pending")
        ready = [
            g for g in pending
            if all(
                self._goals.get(dep, {}).get("status") == "completed"
                for dep in g.get("dependencies", [])
            )
        ]
        blocked = [g for g in pending if g not in ready]
        ready.sort(key=lambda g: (g.get("priority_order", 99), g.get("created_at", "")))
        return ready + blocked

    # ── Estado ──

    def set_status(self, goal_id: str, status: str, progress: str = "") -> None:
        if goal_id in self._goals:
            self._goals[goal_id]["status"] = status
            self._goals[goal_id]["updated_at"] = datetime.now(UTC).isoformat()
            if progress:
                self._goals[goal_id]["progress"] = progress
            self._save_goal(self._goals[goal_id])

    def suspend(self, goal_id: str) -> None:
        """Suspende un objetivo en ejecución."""
        self.set_status(goal_id, "suspended", "Suspendido manualmente")

    def resume(self, goal_id: str) -> None:
        """Reanuda un objetivo suspendido."""
        g = self._goals.get(goal_id)
        if g and g["status"] == "suspended":
            self.set_status(goal_id, "pending", "Reanudado")

    def cancel(self, goal_id: str) -> None:
        """Cancela un objetivo."""
        self.set_status(goal_id, "cancelled", "Cancelado")

    # ── Prioridad dinámica ──

    def reprioritize(self, goal_id: str, new_priority: str) -> None:
        """Cambia la prioridad de un objetivo en caliente."""
        if goal_id in self._goals and new_priority in PRIORITY_ORDER:
            self._goals[goal_id]["priority"] = new_priority
            self._goals[goal_id]["priority_order"] = PRIORITY_ORDER[new_priority]
            self._goals[goal_id]["updated_at"] = datetime.now(UTC).isoformat()
            self._save_goal(self._goals[goal_id])
            self._engine.ledger.add_decision(
                "goal_reprioritized",
                {"goal_id": goal_id, "new_priority": new_priority},
            )

    # ── Dependencias ──

    def add_dependency(self, goal_id: str, depends_on: str) -> None:
        """Añade una dependencia entre objetivos."""
        if goal_id in self._goals and depends_on in self._goals:
            if depends_on not in self._goals[goal_id].setdefault("dependencies", []):
                self._goals[goal_id]["dependencies"].append(depends_on)
                self._save_goal(self._goals[goal_id])

    def blocked_goals(self) -> list[dict[str, Any]]:
        """Retorna objetivos bloqueados por dependencias no cumplidas."""
        blocked = []
        for g in self._goals.values():
            if g["status"] == "pending" and g.get("dependencies"):
                missing = [
                    self._goals.get(dep, {}).get("title", dep)
                    for dep in g["dependencies"]
                    if self._goals.get(dep, {}).get("status") != "completed"
                ]
                if missing:
                    blocked.append({"goal": g, "blocked_by": missing})
        return blocked

    # ── Resumen ──

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self._goals),
            "pending": len(self.list_by_status("pending")),
            "in_progress": len(self.list_by_status("in_progress")),
            "completed": len(self.list_by_status("completed")),
            "suspended": len(self.list_by_status("suspended")),
            "cancelled": len(self.list_by_status("cancelled")),
        }
