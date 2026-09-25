"""Tests para F27-B2: Contratos y Modelos de Agentes.

Cubre:
- Modelos (AgentTask, AgentPlan, AgentResult, etc.)
- StateMachine (transiciones válidas e inválidas)
- CapabilityGate (permisos)
- IDs deterministas
- Todos los ABCs (verificables por herencia)
"""

from __future__ import annotations

import pytest
import pytest

from motor.agents import (
    Agent,
    AgentCapability,
    AgentContext,
    AgentExecution,
    AgentPolicy,
    AgentResult,
    AgentState,
    AgentStateMachine,
    AgentTask,
    AuditLogger,
    CapabilityGate,
    Executor,
    Planner,
    Scheduler,
    StateMachine,
    TaskQueue,
    ToolContract,
    ToolRunner,
    make_agent_id,
    make_plan_id,
    make_step_id,
    make_task_id,
)

# ═══════════════════════════════════════════════════
# B2.1: IDs deterministas
# ═══════════════════════════════════════════════════


@pytest.mark.unit
def test_make_agent_id_deterministic() -> None:
    a = make_agent_id("task1", 1000.0)
    b = make_agent_id("task1", 1000.0)
    assert a == b
    assert len(a) == 16


@pytest.mark.unit
def test_make_task_id_deterministic() -> None:
    a = make_task_id("Find info about X", 1000.0)
    b = make_task_id("Find info about X", 1000.0)
    assert a == b


@pytest.mark.unit
def test_make_plan_id_deterministic() -> None:
    a = make_plan_id("agent1", 1)
    b = make_plan_id("agent1", 1)
    assert a == b


@pytest.mark.unit
def test_make_step_id_deterministic() -> None:
    pid = make_plan_id("a1", 1)
    a = make_step_id(pid, 0)
    b = make_step_id(pid, 0)
    assert a == b


# ═══════════════════════════════════════════════════
# B2.2: Modelos
# ═══════════════════════════════════════════════════


@pytest.mark.unit
def test_agent_task_immutable() -> None:
    t = AgentTask(task_id="t1", objective="test")
    with pytest.raises(AttributeError):
        t.objective = "changed"


@pytest.mark.unit
def test_agent_result_immutable() -> None:
    r = AgentResult(agent_id="a1", task_id="t1", state=AgentState.COMPLETED)
    with pytest.raises(AttributeError):
        r.state = AgentState.FAILED


@pytest.mark.unit
def test_agent_context_mutable() -> None:
    c = AgentContext()
    c.conversation.append({"role": "user", "content": "hello"})
    assert len(c.conversation) == 1


@pytest.mark.unit
def test_agent_execution_defaults() -> None:
    e = AgentExecution(
        agent_id="a1",
        task=AgentTask(task_id="t1", objective="test"),
        capabilities={AgentCapability.MEMORY_READ},
        policy=AgentPolicy(),
    )
    assert e.state == AgentState.CREATED
    assert e.cancelled is False
    assert e.cost_units == 0


@pytest.mark.unit
def test_agent_policy_defaults() -> None:
    p = AgentPolicy()
    assert p.max_duration_seconds == 300
    assert p.max_llm_calls == 50
    assert p.retry_max_attempts == 3


@pytest.mark.unit
def test_tool_contract_defaults() -> None:
    c = ToolContract(name="web.search")
    assert c.timeout_seconds == 30
    assert c.cancelable is True
    assert c.expected_cost_units == 5


@pytest.mark.unit
def test_agent_state_values() -> None:
    assert AgentState.CREATED.value == "created"
    assert AgentState.PERMISSION_DENIED.value == "permission_denied"
    assert AgentState.TOOL_ERROR.value == "tool_error"
    assert AgentState.LLM_ERROR.value == "llm_error"
    assert len(AgentState) == 12


@pytest.mark.unit
def test_capability_values() -> None:
    assert AgentCapability.MEMORY_READ.value == "memory.read"
    assert AgentCapability.FACTS_READ.value == "facts.read"
    assert len(AgentCapability) == 9


# ═══════════════════════════════════════════════════
# B2.3: StateMachine
# ═══════════════════════════════════════════════════


@pytest.mark.unit
def test_valid_transition_created_to_planning() -> None:
    sm = AgentStateMachine()
    assert sm.transition(AgentState.CREATED, AgentState.PLANNING) == AgentState.PLANNING


@pytest.mark.unit
def test_valid_transition_created_to_cancelled() -> None:
    sm = AgentStateMachine()
    assert sm.transition(AgentState.CREATED, AgentState.CANCELLED) == AgentState.CANCELLED


@pytest.mark.unit
def test_invalid_transition_created_to_completed() -> None:
    sm = AgentStateMachine()
    with pytest.raises(ValueError, match="Invalid state transition"):
        sm.transition(AgentState.CREATED, AgentState.COMPLETED)


@pytest.mark.unit
def test_invalid_transition_completed_to_running() -> None:
    sm = AgentStateMachine()
    with pytest.raises(ValueError):
        sm.transition(AgentState.COMPLETED, AgentState.RUNNING)


@pytest.mark.unit
def test_invalid_transition_cancelled_to_running() -> None:
    sm = AgentStateMachine()
    with pytest.raises(ValueError):
        sm.transition(AgentState.CANCELLED, AgentState.RUNNING)


@pytest.mark.unit
def test_full_valid_flow() -> None:
    sm = AgentStateMachine()
    flow = [
        (AgentState.CREATED, AgentState.PLANNING),
        (AgentState.PLANNING, AgentState.READY),
        (AgentState.READY, AgentState.RUNNING),
        (AgentState.RUNNING, AgentState.WAITING),
        (AgentState.WAITING, AgentState.RUNNING),
        (AgentState.RUNNING, AgentState.COMPLETED),
    ]
    state = AgentState.CREATED
    for _, target in flow:
        state = sm.transition(state, target)
    assert state == AgentState.COMPLETED


@pytest.mark.unit
def test_valid_transitions_from_state() -> None:
    sm = AgentStateMachine()
    transitions = sm.valid_transitions(AgentState.RUNNING)
    assert AgentState.COMPLETED in transitions
    assert AgentState.FAILED in transitions
    assert AgentState.CANCELLED in transitions
    assert AgentState.PERMISSION_DENIED in transitions


@pytest.mark.unit
def test_is_terminal() -> None:
    sm = AgentStateMachine()
    assert sm.is_terminal(AgentState.COMPLETED)
    assert sm.is_terminal(AgentState.FAILED)
    assert sm.is_terminal(AgentState.CANCELLED)
    assert not sm.is_terminal(AgentState.RUNNING)
    assert not sm.is_terminal(AgentState.CREATED)


# ═══════════════════════════════════════════════════
# B2.4: ABCs — verificación de interfaces
# ═══════════════════════════════════════════════════


@pytest.mark.unit
def test_capability_gate_is_abc() -> None:
    import inspect

    assert inspect.isabstract(CapabilityGate)


@pytest.mark.unit
def test_planner_is_abc() -> None:
    import inspect

    assert inspect.isabstract(Planner)


@pytest.mark.unit
def test_executor_is_abc() -> None:
    import inspect

    assert inspect.isabstract(Executor)


@pytest.mark.unit
def test_scheduler_is_abc() -> None:
    import inspect

    assert inspect.isabstract(Scheduler)


@pytest.mark.unit
def test_agent_is_abc() -> None:
    import inspect

    assert inspect.isabstract(Agent)


@pytest.mark.unit
def test_tool_runner_is_abc() -> None:
    import inspect

    assert inspect.isabstract(ToolRunner)


@pytest.mark.unit
def test_audit_logger_is_abc() -> None:
    import inspect

    assert inspect.isabstract(AuditLogger)


@pytest.mark.unit
def test_task_queue_is_abc() -> None:
    import inspect

    assert inspect.isabstract(TaskQueue)


@pytest.mark.unit
def test_state_machine_is_abc() -> None:
    import inspect

    assert inspect.isabstract(StateMachine)


# ═══════════════════════════════════════════════════
# B2.5: Todos los símbolos exportados existen
# ═══════════════════════════════════════════════════


@pytest.mark.unit
def test_all_exported_symbols() -> None:
    from motor.agents import __all__

    expected = [
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
    for symbol in expected:
        assert symbol in __all__, f"Missing export: {symbol}"
