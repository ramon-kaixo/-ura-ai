"""PerformanceAgent — benchmarks, profiling, optimización."""

from __future__ import annotations

from typing import Any

from scripts.pro.autonomy.swarm.agent_base import AgentBase


class PerformanceAgent(AgentBase):
    """Mide y optimiza rendimiento del pipeline."""

    def __init__(self, engine) -> None:
        super().__init__("ingeniero", "performance", engine)

    def work(self, goal: dict) -> dict[str, Any]:
        self.log(f"Midiendo rendimiento: {goal.get('title')}")
        disk = self._engine.health_disk()
        ollama = self._engine.health_ollama()
        self.log(f"Disco: {disk.get('libre_gb', '?')}GB libres, Ollama: {len(ollama)} modelos")
        return {"status": "ok", "disco_gb": disk.get("libre_gb", 0), "ollama_modelos": len(ollama)}
