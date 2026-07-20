"""Goal Manager — crear, priorizar y persistir objetivos de autonomía.

NO conoce Planner, Executor ni Evaluator.
Se comunica solo a través del PipelineEngine y el ExecutionLedger.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine


class GoalManager:
    """Gestión de objetivos autónomos."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._goals: dict[str, dict[str, Any]] = {}

    def create(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        budget: dict | None = None,
    ) -> dict[str, Any]:
        goal = {
            "goal_id": uuid.uuid4().hex[:12],
            "title": title,
            "description": description,
            "priority": priority,
            "status": "pending",
            "budget": budget or {"time_max_s": 3600, "changes_max": 50, "cost_max": 10},
            "dependencies": [],
            "tags": [],
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "result": None,
        }
        self._goals[goal["goal_id"]] = goal
        self._engine.ledger.set_goal(goal)
        self._engine.ledger.add_decision(
            "goal_created",
            {"goal_id": goal["goal_id"], "title": title, "priority": priority},
        )
        return goal

    def get(self, goal_id: str) -> dict[str, Any] | None:
        return self._goals.get(goal_id)

    def list_active(self) -> list[dict[str, Any]]:
        return [g for g in self._goals.values() if g["status"] in ("pending", "in_progress")]

    def set_status(self, goal_id: str, status: str) -> None:
        if goal_id in self._goals:
            self._goals[goal_id]["status"] = status
            self._goals[goal_id]["updated_at"] = datetime.now(UTC).isoformat()
