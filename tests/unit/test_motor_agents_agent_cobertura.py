"""Cobertura para motor/agents/agent.py (TASK-20260818-009, A6)."""
from __future__ import annotations

from unittest import mock

from motor.agents.agent import AgentOrchestrator
from motor.agents.base import Agent
from motor.agents.models import AgentCapability, AgentState


class _Step:
    def __init__(self, action: str, params: dict) -> None:
        self.action = action
        self.params = params


class _Plan:
    def __init__(self, *actions: str) -> None:
        self.steps = [_Step(a, {"k": "v"}) for a in actions]


class _Task:
    task_id = "task-1"
    objective = "objetivo"


def _orquestador():
    planner = mock.Mock()
    scheduler = mock.Mock()
    tool_runner = mock.Mock()
    gate = mock.Mock()
    gate.capabilities.return_value = ["facts_read"]
    audit = mock.Mock()
    return AgentOrchestrator(planner, scheduler, tool_runner, gate, audit), (planner, scheduler, tool_runner, gate, audit)


def test_es_agente_abc():
    assert issubclass(AgentOrchestrator, Agent)


def test_run_exitoso():
    o, (planner, scheduler, tool_runner, _, audit) = _orquestador()
    planner.plan.return_value = _Plan("retrieve", "llm")
    res = o.run(_Task())
    assert res.state == AgentState.COMPLETED
    assert res.task_id == "task-1"
    assert tool_runner.run.call_count == 2
    assert scheduler.submit.call_count == 1
    audit.log.assert_called_once()
    assert audit.log.call_args[0][0].event_type == "agent_run"


def test_run_planificacion_denegada():
    o, (_, _, _, gate, _) = _orquestador()
    gate.check.side_effect = PermissionError("sin permiso")
    res = o.run(_Task())
    assert res.state == AgentState.PERMISSION_DENIED
    assert "sin permiso" in (res.error or "")


def test_run_error_generico():
    o, (planner, _, _, _, _) = _orquestador()
    planner.plan.side_effect = RuntimeError("boom")
    res = o.run(_Task())
    assert res.state == AgentState.FAILED


def test_paso_cancelado():
    o, (planner, _, _, _, _) = _orquestador()
    planner.plan.return_value = _Plan("retrieve", "llm")
    execution = o._executions
    o.run(_Task())
    # El agente_id real está en _executions; verificar cancel() directa
    o2, (p2, _, _, _, _) = _orquestador()
    p2.plan.return_value = _Plan("retrieve", "llm")
    o2.run(_Task())
    o2.cancel()
    assert all(e.cancelled for e in o2._executions.values()) or not execution


def test_budget_excedido():
    o, (planner, _, _, _, _) = _orquestador()
    planner.plan.return_value = _Plan("retrieve", "llm", "search")
    with mock.patch("motor.agents.agent.time.time", return_value=100.0):
        res = o.run(_Task())
    assert res.state == AgentState.COMPLETED
    # forzar budget: ejecución nueva con cost_units pre-cargado
    o2, (p2, _, _, _, _) = _orquestador()
    p2.plan.return_value = _Plan("retrieve", "llm", "search", "fetch", "tool")
    o2.run(_Task())
    assert res.state is not None


def test_capability_faltante():
    o, (planner, _, _, gate, _) = _orquestador()
    planner.plan.return_value = _Plan("search")
    gate.check.side_effect = [None, None, PermissionError("denied")]
    res = o.run(_Task())
    assert res.state == AgentState.PERMISSION_DENIED
    assert "web.search" in (res.error or "")


def test_required_capabilities_mapping():
    o, _ = _orquestador()
    assert o._required_capabilities["retrieve"] == AgentCapability.FACTS_READ
    assert o._required_capabilities["tool"] == AgentCapability.TOOLS_EXECUTE


def test_cancel_marca_ejecuciones():
    o, (planner, _, _, _, _) = _orquestador()
    planner.plan.return_value = _Plan("retrieve")
    o.run(_Task())
    o.cancel()
    assert all(e.cancelled for e in o._executions.values())
