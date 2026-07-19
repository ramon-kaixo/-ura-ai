"""F27 — Modelos de datos de Agentes.

Contratos y tipos de datos. Sin lógica de negocio.
"""

from __future__ import annotations

import hashlib
import json
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
    max_context_entries: int = 1000
    max_memory_bytes: int = 50 * 1024 * 1024  # 50 MB


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


# ── ToolRunner ─────────────────────────────


@dataclass(frozen=True)
class ToolRequest:
    execution_id: str
    tool_name: str
    params: dict
    timeout: int = 30
    attempt: int = 1
    protocol_version: str = "1.0"
    trace_id: str = ""
    causation_id: str = ""

    def to_envelope(self) -> ProtocolEnvelope:  # noqa: F821
        from motor.platform.models import (
            CausationId,
            CorrelationId,
            DeliveryHeader,
            MessageKind,
            RoutingHeader,
            SpanId,
            TraceHeader,
            TraceId,
            VersionHeader,
        )
        from motor.platform.serializer import make_envelope_with_checksum, make_message_id

        payload = json.dumps(
            {
                "execution_id": self.execution_id,
                "tool_name": self.tool_name,
                "params": self.params,
                "timeout": self.timeout,
                "attempt": self.attempt,
                "protocol_version": self.protocol_version,
            },
        ).encode("utf-8")

        return make_envelope_with_checksum(
            version=VersionHeader(
                protocol_version=self.protocol_version,
                schema_version="1.0",
                payload_type="json",
            ),
            routing=RoutingHeader(
                message_id=make_message_id(
                    self.protocol_version,
                    "1.0",
                    "agent",
                    self.tool_name,
                    "ToolRequest",
                    payload,
                ),
                message_type="ToolRequest",
                message_kind=MessageKind.COMMAND,
                source="agent",
                destination=self.tool_name,
            ),
            trace=TraceHeader(
                trace_id=TraceId(self.trace_id) if self.trace_id else TraceId.generate(),
                span_id=SpanId(self.execution_id),
                correlation_id=CorrelationId(self.execution_id),
                causation_id=CausationId(self.causation_id) if self.causation_id else CausationId.root(),
            ),
            delivery=DeliveryHeader(timeout_ms=self.timeout * 1000),
            payload=payload,
        )

    @classmethod
    def from_envelope(cls, envelope: ProtocolEnvelope) -> ToolRequest:  # noqa: F821
        data = json.loads(envelope.payload.decode("utf-8"))
        return cls(
            execution_id=data["execution_id"],
            tool_name=data["tool_name"],
            params=data["params"],
            timeout=data.get("timeout", 30),
            attempt=data.get("attempt", 1),
            protocol_version=data.get("protocol_version", "1.0"),
            trace_id=str(envelope.trace.trace_id) if envelope.trace.trace_id else "",
            causation_id=str(envelope.trace.causation_id) if envelope.trace.causation_id else "",
        )


@dataclass(frozen=True)
class ToolResult:
    execution_id: str
    tool_name: str
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    duration_ms: float = 0.0
    attempt: int = 1
    protocol_version: str = "1.0"

    def to_envelope(self) -> ProtocolEnvelope:  # noqa: F821
        from motor.platform.models import (
            DeliveryHeader,
            MessageKind,
            RoutingHeader,
            TraceHeader,
            VersionHeader,
        )
        from motor.platform.serializer import make_envelope_with_checksum, make_message_id

        payload = json.dumps(
            {
                "execution_id": self.execution_id,
                "tool_name": self.tool_name,
                "success": self.success,
                "data": self.data,
                "error": self.error,
                "error_type": self.error_type,
                "duration_ms": self.duration_ms,
                "attempt": self.attempt,
                "protocol_version": self.protocol_version,
            },
        ).encode("utf-8")

        return make_envelope_with_checksum(
            version=VersionHeader(
                protocol_version=self.protocol_version,
                schema_version="1.0",
                payload_type="json",
            ),
            routing=RoutingHeader(
                message_id=make_message_id(
                    self.protocol_version,
                    "1.0",
                    self.tool_name,
                    "agent",
                    "ToolResult",
                    payload,
                ),
                message_type="ToolResult",
                message_kind=MessageKind.RESPONSE,
                source=self.tool_name,
                destination="agent",
            ),
            trace=TraceHeader(
                trace_id=self.execution_id,
                span_id=self.execution_id,
                correlation_id=self.execution_id,
            ),
            delivery=DeliveryHeader(),
            payload=payload,
        )

    @classmethod
    def from_envelope(cls, envelope: ProtocolEnvelope) -> ToolResult:  # noqa: F821
        data = json.loads(envelope.payload.decode("utf-8"))
        return cls(
            execution_id=data["execution_id"],
            tool_name=data["tool_name"],
            success=data["success"],
            data=data.get("data", {}),
            error=data.get("error"),
            error_type=data.get("error_type"),
            duration_ms=data.get("duration_ms", 0.0),
            attempt=data.get("attempt", 1),
            protocol_version=data.get("protocol_version", "1.0"),
        )


def make_tool_execution_id(agent_id: str, tool_name: str, timestamp: float) -> str:
    raw = f"{agent_id}:{tool_name}:{int(timestamp)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
