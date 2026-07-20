"""ArchitectureAgent — deuda técnica, refactorización, estructura del código."""

from __future__ import annotations

from typing import Any

from scripts.pro.autonomy.swarm.agent_base import AgentBase


class ArchitectureAgent(AgentBase):
    """Evalúa arquitectura, deuda técnica y propone refactors."""

    def __init__(self, engine) -> None:
        super().__init__("arquitecto", "architecture", engine)

    def work(self, goal: dict) -> dict[str, Any]:
        self.log(f"Analizando arquitectura: {goal.get('title')}")
        ruff = self._engine.run_ruff(["check", "--select", "F821,F841", ".", "--output-format", "concise"])
        f821 = ruff.stdout.count("F821")
        f841 = ruff.stdout.count("F841")
        self.log(f"F821: {f821}, F841: {f841}")
        return {"status": "ok" if ruff.returncode == 0 else "issues", "f821": f821, "f841": f841}
