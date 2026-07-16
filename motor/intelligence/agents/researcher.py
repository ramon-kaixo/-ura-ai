"""ResearcherAgent — consulta memoria episódica y semántica para proporcionar contexto."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentRole, AgentStatus, AgentTask

log = logging.getLogger("ura.agent.researcher")


class ResearcherAgent(Agent):
    def __init__(
        self,
        agent_id: str = "",
        memory_store: Any = None,
        context_retriever: Any = None,
    ) -> None:
        self.id = agent_id or uuid.uuid4().hex[:12]
        self.name = "researcher"
        self.role = AgentRole.RESEARCHER
        self.capabilities = ["search", "retrieve", "lookup"]
        self.status = AgentStatus.IDLE
        self._memory_store = memory_store
        self._context_retriever = context_retriever
        if self._memory_store is None or self._context_retriever is None:
            self._auto_discover()

    def _auto_discover(self) -> None:
        try:
            from motor.intelligence.memory.episodic import EpisodeStore
            from motor.intelligence.memory.retrieval import ContextRetriever

            if self._context_retriever is None:
                self._context_retriever = ContextRetriever(EpisodeStore())
        except Exception:
            pass
        try:
            from motor.intelligence.memory.semantic import SemanticMemoryStore

            if self._memory_store is None:
                self._memory_store = SemanticMemoryStore()
        except Exception:
            pass

    def run(self, task: AgentTask) -> AgentResult:
        start = time.monotonic()
        self.status = AgentStatus.BUSY
        try:
            context = self._gather_context(task.objective, task.context)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=True,
                output=context,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as exc:
            log.warning("ResearcherAgent error: %s", exc)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )
        finally:
            self.status = AgentStatus.IDLE

    def _gather_context(self, objective: str, context: dict) -> dict[str, Any]:
        results: dict[str, Any] = {"query": objective, "sources": []}

        # Try semantic memory store
        if self._memory_store:
            facts = self._memory_store.search(text=objective, k=5)
            if facts:
                results["semantic_facts"] = [f.to_dict() for f in facts]
                results["sources"].append("semantic_memory")

        # Try context retriever (episodic memory)
        if self._context_retriever:
            from motor.intelligence.memory.retrieval import ContextQuery

            query = ContextQuery(text=objective, k=5)
            episodes = self._context_retriever.search(query)
            if episodes:
                results["episodes"] = episodes.to_dict()
                results["sources"].append("episodic_memory")

        return results
