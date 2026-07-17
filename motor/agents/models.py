"""F27 — Modelos de datos de Agentes.

Contratos y tipos de datos. Sin lógica de negocio.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum


# ── IDs deterministas ─────────────────────


def make_agent_id(task_id: str, created_at: float) -> str:
    raw = f"{task_id}:{int(created_at)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_task_id(objective: str, timestamp: float) -> str:
    raw = f"{objective.strip().lower()}:{int(timestamp)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_plan_id(agent_id: str, attempt: int) -> str:
    raw = f"{agent_id}:plan:{attempt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_step_id(plan_id: str, index: int) -> str:
    raw = f"{plan_id}:step:{index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── Enums ────────────────────────────────


class AgentState(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    TOOL_ERROR = "tool_error"
    LLM_ERROR = "llm_error"


class AgentCapability(StrEnum):
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    FACTS_READ = "facts.read"
    WEB_SEARCH = "web.search"
    WEB_FETCH = "web.fetch"
    TOOLS_EXECUTE = "tools.execute"
    AGENTS_SPAWN = "agents.spawn"
    AGENTS_MESSAGE = "agents.message"
    CONFIG_READ = "config.read"


# ── Modelos ──────────────────────────────


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    objective: str
    max_steps: int = 10
    created_at: float = 0.0


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    action: str
    params: dict = field(default_factory=dict)
    depends_on: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AgentPlan:
    plan_id: str
    steps: tuple[PlanStep, ...] = field(default_factory=tuple)
    immutable: bool = True


@dataclass
class AgentContext:
    conversation: list[dict] = field(default_factory=list)
    knowledge_facts: list[str] = field(default_factory=list)
    memory_entries: list[str] = field(default_factory=list)
    execution_state: dict = field(default_factory=dict)


@dataclass
class AgentPolicy:
    max_duration_seconds: int = 300
    max_cost_units: int = 1000
    max_llm_calls: int = 50
    max_tool_calls: int = 20
    max_plan_depth: int = 5
    max_subagents: int = 3
    timeout_per_step: int = 60
    cancel_on_timeout: bool = True
    retry_max_attempts: int = 3
    backoff_base_seconds: float = 1.0


@dataclass
class AgentExecution:
    agent_id: str
    task: AgentTask
    capabilities: set[AgentCapability]
    policy: AgentPolicy
    context: AgentContext = field(default_factory=AgentContext)
    state: AgentState = AgentState.CREATED
    current_step: int = 0
    start_time: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    cost_units: int = 0
    cancelled: bool = False
    plan: AgentPlan | None = None
    plan_attempts: int = 0


@dataclass(frozen=True)
class AgentResult:
    agent_id: str
    task_id: str
    state: AgentState
    output: str = ""
    steps_completed: int = 0
    duration_ms: float = 0.0
    cost_units: int = 0
    error: str | None = None
    audit: AgentAuditRecord | None = None


@dataclass(frozen=True)
class AgentAuditRecord:
    agent_id: str
    task_id: str
    objective: str
    plan: list[str]
    capabilities_used: list[str]
    tools_used: list[str]
    facts_consulted: list[str]
    memory_consulted: list[str]
    llm_calls: int
    decisions: list[dict]
    result: str
    state: str
    duration_ms: float
    cost_units: int
    error: str | None
    timestamp: float
    parent_agent: str | None = None


@dataclass(frozen=True)
class ToolContract:
    name: str
    timeout_seconds: int = 30
    cancelable: bool = True
    idempotent: bool = False
    side_effects: list[str] = field(default_factory=list)
    expected_cost_units: int = 5
    description: str = ""


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    agent_id: str
    timestamp: float
    data: dict = field(default_factory=dict)
