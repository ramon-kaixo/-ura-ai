"""Ejecutor que traduce propuestas del cerebro en tareas de tuneladora."""
from __future__ import annotations

from typing import Any


class ProposalExecutor:
    def to_tuneladora_task(self, proposal: dict[str, Any]) -> dict[str, Any]:
        task_types = {
            "refactor": "code_quality",
            "split": "refactor",
            "test": "testing",
            "doc": "documentation",
        }
        return {
            "plugin": task_types.get(proposal["type"], "generic"),
            "target": proposal["target"],
            "params": proposal,
            "priority": proposal.get("priority", "low"),
        }
