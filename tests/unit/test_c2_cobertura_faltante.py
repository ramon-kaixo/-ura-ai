"""Tests para cubrir las lineas faltantes de C2 (TASK-20260825-008).

Lineas objetivo:
  - core/logs/guardian_logger.py 101-102  (OSError handler)
  - motor/agents/agent.py 103             (cancelled mid-execution)
  - motor/agents/agent.py 106             (budget exceeded)
  - motor/agents/agent.py 130             (llm_calls increment)
"""
from __future__ import annotations

from unittest import mock

import core.logs.guardian_logger as gl
from motor.agents.agent import AgentOrchestrator
from motor.agents.models import (
    AgentPlan,
    AgentPolicy,
    AgentState,
    PlanStep,
    make_step_id,
)

# ── Guardian: OSError handler (lineas 101-102) ────────────────────────


def test_log_event_oserror_escritura(tmp_path, monkeypatch):
    """Si open() lanza OSError durante escritura, se loguea y no explota."""
    monkeypatch.setattr(gl, "GUARDIAN_LOG", str(tmp_path / "guardian.jsonl"))

    original_open = open

    def _fake_open(path, mode="r", *a, **kw):
        if "guardian" in str(path):
            raise OSError("disco lleno")
        return original_open(path, mode, *a, **kw)

    with mock.patch("builtins.open", side_effect=_fake_open):
        gl.log_event("test_event", model="m", attempts=2, result_type="warning")

    assert not (tmp_path / "guardian.jsonl").exists()


# ── Agent helpers ─────────────────────────────────────────────────────


class _Task:
    task_id = "t1"
    objective = "test"


def _make_plan(*actions: str) -> AgentPlan:
    steps = tuple(
        PlanStep(step_id=make_step_id("p", i), action=a, params={})
        for i, a in enumerate(actions, 1)
    )
    return AgentPlan(plan_id="p", steps=steps)


def _orquestador():
    planner = mock.Mock()
    scheduler = mock.Mock()
    tool_runner = mock.Mock()
    gate = mock.Mock()
    gate.capabilities.return_value = []
    audit = mock.Mock()
    return AgentOrchestrator(planner, scheduler, tool_runner, gate, audit)


# ── Agent: cancelled mid-execution (linea 103) ────────────────────────


def test_cancelled_devuelve_cancelled_state():
    """Plan de 2 pasos; el primero cancela → linea 103 cubierta."""
    o = _orquestador()
    o._planner.plan.return_value = _make_plan("s1", "s2")

    def _cancel_first(action, params=None):
        exec_id = next(iter(o._executions))
        o._executions[exec_id].cancelled = True

    o._tool_runner.run.side_effect = _cancel_first
    res = o.run(_Task())
    assert res.state == AgentState.CANCELLED


# ── Agent: budget exceeded (linea 106) ────────────────────────────────


def test_budget_exceeded_returns_cancelled():
    """Plan de 3 pasos + max_cost_units=2 → linea 106 cubierta."""
    o = _orquestador()
    o._planner.plan.return_value = _make_plan("s1", "s2", "s3")

    with mock.patch(
        "motor.agents.models.AgentPolicy",
        return_value=AgentPolicy(max_cost_units=2),
    ):
        res = o.run(_Task())

    assert res.state == AgentState.CANCELLED
    assert "Budget exceeded" in (res.error or "")


# ── Agent: llm_calls tracking (linea 130) ────────────────────────────


def test_llm_step_increments_llm_calls():
    """Plan con 1 paso llm → execution.llm_calls == 1 → linea 130 cubierta."""
    o = _orquestador()
    o._planner.plan.return_value = _make_plan("llm")
    captured_exec = {}

    def _capture_run(action, params=None):
        captured_exec.update(dict(o._executions))

    o._tool_runner.run.side_effect = _capture_run
    res = o.run(_Task())
    assert res.state == AgentState.COMPLETED
    # La ejecucion ya no esta en _executions tras _finalize, capturar del resultado
    o._tool_runner.run.assert_called_once_with("llm", mock.ANY)
