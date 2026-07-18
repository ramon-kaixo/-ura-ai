"""Agentes Autónomos (F27).

Contratos, modelos y componentes del sistema de agentes.

Clasificación de API:
- 🟢 ESTABLE (compatibilidad garantizada):
    Agent, AgentState, AgentCapability, CapabilityGate,
    AgentCapabilityGate, DenialCode,
    Scheduler, Planner, Executor, ToolRunner, ToolAdapter,
    StateMachine, AgentToolRunner

- 🟡 ADVANCED (extensión, sin garantía de compatibilidad):
    AgentTask, AgentPlan, AgentResult, AgentContext,
    AgentPolicy, AgentExecution, AgentAuditRecord,
    ToolContract, ToolRequest, ToolResult,
    AuditEvent, TaskQueue, AuditLogger,
    PermissionDecision,
    ToolError, ToolTimeoutError, ToolCancelledError,
    ToolTransientError, ToolPermanentError, ToolNotFoundError

- 🔵 INTERNA (no exportar desde este paquete):
    make_agent_id, make_task_id, make_plan_id, make_step_id,
    make_tool_execution_id, PlanStep, AgentStateMachine,
    ToolAdapterError
"""

from motor.agents.base import (
    Agent,
    AuditLogger,
    CapabilityGate,
    Executor,
    Planner,
    Scheduler,
    StateMachine,
    TaskQueue,
    ToolAdapter,
    ToolRunner,
)
from motor.agents.gate import AgentCapabilityGate, DenialCode, PermissionDecision
from motor.agents.models import (
    AgentAuditRecord,
    AgentCapability,
    AgentContext,
    AgentExecution,
    AgentPlan,
    AgentPolicy,
    AgentResult,
    AgentState,
    AgentTask,
    AuditEvent,
    PlanStep,
    ToolContract,
    ToolRequest,
    ToolResult,
    make_agent_id,
    make_plan_id,
    make_step_id,
    make_task_id,
    make_tool_execution_id,
)
from motor.agents.runner import (
    AgentToolRunner,
    ToolAdapterError,
    ToolCancelledError,
    ToolError,
    ToolNotFoundError,
    ToolPermanentError,
    ToolTimeoutError,
    ToolTransientError,
)
from motor.agents.scheduler import AgentScheduler
from motor.agents.state import AgentStateMachine

__all__ = [
    "Agent",
    "AgentAuditRecord",
    "AgentCapability",
    "AgentCapabilityGate",
    "AgentContext",
    "AgentExecution",
    "AgentPlan",
    "AgentPolicy",
    "AgentResult",
    "AgentState",
    "AgentStateMachine",
    "AgentTask",
    "AgentScheduler",
    "AgentToolRunner",
    "AuditEvent",
    "AuditLogger",
    "CapabilityGate",
    "DenialCode",
    "Executor",
    "PermissionDecision",
    "PlanStep",
    "Planner",
    "Scheduler",
    "StateMachine",
    "TaskQueue",
    "ToolAdapter",
    "ToolAdapterError",
    "ToolCancelledError",
    "ToolContract",
    "ToolError",
    "ToolNotFoundError",
    "ToolPermanentError",
    "ToolRequest",
    "ToolResult",
    "ToolRunner",
    "ToolTimeoutError",
    "ToolTransientError",
    "make_agent_id",
    "make_plan_id",
    "make_step_id",
    "make_task_id",
    "make_tool_execution_id",
]
