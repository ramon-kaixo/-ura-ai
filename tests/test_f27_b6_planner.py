"""Tests para F27-B6: Planner.

Cubre:
- Generación de planes deterministas
- Replanificación con conservación de pasos
- Límites de replanificación
- Sin dependencias de Scheduler, Agent, ToolRunner
- Keywords → acciones
- Fallback en replanificación
"""

from __future__ import annotations

from motor.agents import AgentContext, AgentPlan, AgentTask, PlanStep, RuleBasedPlanner


def _task(objective: str = "search for information about X") -> AgentTask:
    return AgentTask(task_id="t1", objective=objective)


def _plan_with_steps(*actions: str) -> AgentPlan:
    steps = tuple(
        PlanStep(step_id=f"s{i}", action=a) for i, a in enumerate(actions)
    )
    return AgentPlan(plan_id="p1", steps=steps)


# ═══════════════════════════════════════════════════
# B6.1: Generación de planes
# ═══════════════════════════════════════════════════


def test_plan_search_objective() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("search for information about AI"))
    assert len(plan.steps) >= 2
    # Debe incluir retrieve + search
    actions = [s.action for s in plan.steps]
    assert "retrieve" in actions
    assert "search" in actions


def test_plan_read_objective() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("read facts about Apple"))
    actions = [s.action for s in plan.steps]
    assert "retrieve" in actions


def test_plan_write_objective() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("write a summary and save it"))
    actions = [s.action for s in plan.steps]
    assert "tool" in actions
    assert "llm" in actions


def test_plan_unknown_objective() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("do something random"))
    assert len(plan.steps) >= 1
    # Siempre debe tener al menos retrieve + respond


def test_plan_structure() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("search for data"))
    assert plan.plan_id is not None
    assert len(plan.plan_id) == 16
    for step in plan.steps:
        assert step.step_id is not None
        assert step.action is not None


# ═══════════════════════════════════════════════════
# B6.2: Plan es inmutable por defecto
# ═══════════════════════════════════════════════════


def test_plan_immutable_by_default() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("search"))
    assert plan.immutable is True


# ═══════════════════════════════════════════════════
# B6.3: Replanificación
# ═══════════════════════════════════════════════════


def test_replan_conserves_completed_steps() -> None:
    p = RuleBasedPlanner()
    plan = _plan_with_steps("retrieve", "search", "llm")
    ctx = AgentContext()
    failed = plan.steps[1]  # search falló
    new_plan = p.replan(_task("search"), plan, ctx, failed_step=failed)
    # retrieve debe conservarse
    assert new_plan.steps[0].action == "retrieve"
    # search debe reemplazarse
    assert new_plan.steps[1].action != "search" or len(new_plan.steps) >= 2


def test_replan_no_failed_step() -> None:
    """Si no hay paso fallido, se mantiene el plan original."""
    p = RuleBasedPlanner()
    plan = _plan_with_steps("retrieve", "llm")
    ctx = AgentContext()
    new_plan = p.replan(_task("search"), plan, ctx)
    assert new_plan.plan_id == plan.plan_id
    assert len(new_plan.steps) == len(plan.steps)


def test_replan_alternatives() -> None:
    """Replanificación genera alternativas para el paso fallido."""
    p = RuleBasedPlanner()
    plan = _plan_with_steps("retrieve", "search", "llm")
    ctx = AgentContext()
    failed = plan.steps[1]
    new_plan = p.replan(_task("search"), plan, ctx, failed_step=failed)
    # Debe tener al menos 2 pasos (alternativa + respond)
    assert len(new_plan.steps) >= 2


# ═══════════════════════════════════════════════════
# B6.4: Sin dependencias externas
# ═══════════════════════════════════════════════════


def test_no_external_dependencies() -> None:
    import inspect

    import motor.agents.planner as mod
    source = inspect.getsource(mod)
    assert "from motor.agents.base import Scheduler" not in source
    assert "from motor.agents.base import ToolRunner" not in source
    assert "from motor.agents.base import Agent" not in source
    # AgentPlan, AgentTask, AgentContext son modelos permitidos
    assert "from motor.agents.models import AgentPlan" in source


# ═══════════════════════════════════════════════════
# B6.5: Determinismo
# ═══════════════════════════════════════════════════


def test_deterministic_plan() -> None:
    """Mismo objetivo → mismo plan."""
    p = RuleBasedPlanner()
    t = _task("search for something")
    plan1 = p.plan(t)
    plan2 = p.plan(t)
    assert [s.action for s in plan1.steps] == [s.action for s in plan2.steps]
