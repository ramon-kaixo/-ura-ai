"""DocumentationAgent — README, diagramas, ADRs, documentación técnica."""

from __future__ import annotations

from typing import Any

from scripts.pro.autonomy.swarm.agent_base import AgentBase


class DocumentationAgent(AgentBase):
    """Verifica y genera documentación del proyecto."""

    def __init__(self, engine) -> None:
        super().__init__("escriba", "documentation", engine)

    def work(self, goal: dict) -> dict[str, Any]:
        self.log(f"Verificando documentación: {goal.get('title')}")
        readme = self._engine.run_script("scripts/pro/revisor.py", args=["--quick"], timeout=60)
        self.log(f"Revisión completada (exit={readme.returncode})")
        return {"status": "ok", "docs_score": readme.returncode}
