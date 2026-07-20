"""TestingAgent — cobertura, integración, regresión."""

from __future__ import annotations

from typing import Any

from scripts.pro.autonomy.swarm.agent_base import AgentBase


class TestingAgent(AgentBase):
    """Ejecuta tests y mide cobertura."""

    def __init__(self, engine) -> None:
        super().__init__("verificador", "testing", engine)

    def work(self, goal: dict) -> dict[str, Any]:
        self.log(f"Ejecutando tests: {goal.get('title')}")
        result = self._engine.run_script("scripts/pro/revisor.py", args=["--quick"], timeout=120)
        self.log(f"Tests ejecutados (exit={result.returncode})")
        return {"status": "ok" if result.returncode == 0 else "issues", "tests_exit": result.returncode}
