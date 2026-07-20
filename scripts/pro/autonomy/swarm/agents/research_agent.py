"""ResearchAgent — explora nuevas bibliotecas, patrones, tecnologías.

Usa SemanticMemory para analizar el historial y proponer mejoras.
"""

from __future__ import annotations

from typing import Any

from scripts.pro.autonomy.swarm.agent_base import AgentBase


class ResearchAgent(AgentBase):
    """Investigación de nuevas herramientas y patrones."""

    def __init__(self, engine) -> None:
        super().__init__("explorador", "research", engine)

    def work(self, goal: dict) -> dict[str, Any]:
        self.log(f"Investigando: {goal.get('title')}")
        db_path = self._engine.config.nervioso / "memory" / "semantic.db"
        if db_path.exists():
            from scripts.pro.autonomy.research import Researcher
            r = Researcher(db_path)
            result = r.research()
            r.close()
            self.log(f"Hipótesis: {result['total_hipotesis']}")
            return {"status": "ok", "hipotesis": result['total_hipotesis'], "conclusiones": result.get('conclusiones', [])}
        return {"status": "ok", "hipotesis": 0, "conclusiones": []}
