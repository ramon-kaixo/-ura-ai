"""Agentes Autónomos (F27).

Contratos, modelos y componentes del sistema de agentes.

Clasificación de API (Observación B2A):
- 🟢 ESTABLE: Agent, AgentState, AgentCapability, CapabilityGate,
    Scheduler, Planner, Executor, ToolRunner, StateMachine
- 🟡 EXPERIMENTAL: AgentTask, AgentPlan, AgentResult, AgentContext,
    AgentPolicy, AgentExecution, AgentAuditRecord, ToolContract,
    AuditEvent, TaskQueue, AuditLogger
- 🔵 INTERNA: make_agent_id, make_task_id, make_plan_id, make_step_id,
    PlanStep, AgentStateMachine
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
    ToolRunner,
)
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
    make_agent_id,
    make_plan_id,
    make_step_id,
    make_task_id,
)
from motor.agents.state import AgentStateMachine

__all__ = [
    "Agent",
    "AgentAuditRecord",
    "AgentCapability",
    "AgentContext",
    "AgentExecution",
    "AgentPlan",
    "AgentPolicy",
    "AgentResult",
    "AgentState",
    "AgentStateMachine",
    "AgentTask",
    "AuditEvent",
    "AuditLogger",
    "CapabilityGate",
    "Executor",
    "PlanStep",
    "Planner",
    "Scheduler",
    "StateMachine",
    "TaskQueue",
    "ToolContract",
    "ToolRunner",
    "make_agent_id",
    "make_plan_id",
    "make_step_id",
    "make_task_id",
]
