"""AgentMessage, AgentTask, AgentResult, AgentRole, AgentStatus — contratos tipados."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class AgentRole(Enum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
    SUPERVISOR = "supervisor"


class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class AgentMessage:
    source: str
    target: str
    message_type: str  # task | result | error | cancel | status
    payload: dict[str, Any]
    correlation_id: str = ""
    id: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:16]
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()
        if not self.correlation_id:
            self.correlation_id = self.id


@dataclass
class AgentTask:
    objective: str
    agent_role: AgentRole = AgentRole.EXECUTOR
    context: dict[str, Any] = field(default_factory=dict)
    input_data: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    priority: int = 0
    timeout: int = 60
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:16]
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()


@dataclass
class AgentResult:
    task_id: str
    agent_id: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:16]
