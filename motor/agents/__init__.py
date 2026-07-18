"""Agentes Autónomos (F27).

Contratos, modelos y componentes del sistema de agentes.

Clasificación de API (42 símbolos exportados):
- 🟢 ESTABLE (12): Agent, AgentCapability, AgentCapabilityGate,
    AgentScheduler, AgentState, AgentToolRunner, CapabilityGate,
    DenialCode, Scheduler, StateMachine, ToolAdapter, ToolRunner

- 🟡 ADVANCED (17): AgentAuditRecord, AgentContext, AgentExecution,
    AgentPlan, AgentPolicy, AgentResult, AgentTask, AuditEvent,
    AuditLogger, Executor, PermissionDecision, Planner, TaskQueue,
    ToolContract, ToolError, ToolRequest, ToolResult

- 🔵 INTERNA (13): AgentStateMachine, make_agent_id,
    make_plan_id, make_step_id, make_task_id,
    make_tool_execution_id, PlanStep, ToolAdapterError,
    ToolCancelledError, ToolNotFoundError, ToolPermanentError,
    ToolTimeoutError, ToolTransientError
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
from motor.agents.planner import RuleBasedPlanner
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
    "RuleBasedPlanner",
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
