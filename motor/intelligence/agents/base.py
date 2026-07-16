"""Agent (ABC) — interfaz base para todos los agentes."""

from __future__ import annotations

from abc import ABC, abstractmethod

from motor.intelligence.agents.message import AgentResult, AgentRole, AgentStatus, AgentTask


class Agent(ABC):
    id: str
    name: str
    role: AgentRole
    capabilities: list[str]
    status: AgentStatus = AgentStatus.IDLE

    @abstractmethod
    def run(self, task: AgentTask) -> AgentResult: ...

    def can_handle(self, task: AgentTask) -> bool:
        return task.agent_role == self.role
