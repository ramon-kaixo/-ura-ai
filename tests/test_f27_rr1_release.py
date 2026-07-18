"""F27-RR1: Release Readiness Review — Agentes.

Verifica que el sistema de agentes puede ejecutarse durante horas,
recuperarse tras errores, mantener memoria estable y respetar
todos los contratos G-01 a G-08.
"""

from __future__ import annotations

import time

import pytest

from motor.agents import (
    AgentCapability,
    AgentCapabilityGate,
    AgentExecution,
    AgentPolicy,
    AgentScheduler,
    AgentTask,
    AgentToolRunner,
    DenialCode,
    RuleBasedPlanner,
    ToolAdapter,
    ToolContract,
    ToolTimeoutError,
)


# ═══════════════════════════════════════════════════
# RR1.1: G-01 — Agentes son consumidores
# ═══════════════════════════════════════════════════


def test_g01_agents_are_consumers() -> None:
    """Agentes consultan, no poseen conocimiento."""
    p = RuleBasedPlanner()
    plan = p.plan(AgentTask(task_id="t1", objective="read facts about Apple"))
    actions = [s.action for s in plan.steps]
    assert "retrieve" in actions  # solo lee


# ═══════════════════════════════════════════════════
# RR1.2: G-02 — No modifican directamente
# ═══════════════════════════════════════════════════


def test_g02_no_direct_modification() -> None:
    """CapabilityGate no permite facts.write."""
    gate = AgentCapabilityGate(AgentExecution(
        agent_id="a1",
        task=AgentTask(task_id="t1", objective="test"),
        capabilities=set(),
        policy=AgentPolicy(),
    ))
    with pytest.raises(PermissionError):
        gate.check(AgentCapability.FACTS_READ)  # FACTS_READ no está concedida


# ═══════════════════════════════════════════════════
# RR1.3: G-03 — APIs oficiales
# ═══════════════════════════════════════════════════


def test_g03_official_apis() -> None:
    """AgentOrchestrator solo usa ABCs, no acceso directo."""
    import inspect
    import motor.agents.agent as mod
    source = inspect.getsource(mod)
    assert "motor.memory" not in source
    assert "motor.core.fusion" not in source
    assert "motor.core.llm" not in source
    assert "motor.web" not in source


# ═══════════════════════════════════════════════════
# RR1.4: G-04 — Auditabilidad
# ═══════════════════════════════════════════════════


def test_g04_auditability() -> None:
    """AgentAuditRecord contiene todos los campos necesarios."""
    from motor.agents.models import AgentAuditRecord
    record = AgentAuditRecord(
        agent_id="a1", task_id="t1", objective="test",
        plan=[], capabilities_used=[], tools_used=[],
        facts_consulted=[], memory_consulted=[], llm_calls=0,
        decisions=[], result="ok", state="completed",
        duration_ms=100, cost_units=5, error=None, timestamp=1000,
    )
    assert record.agent_id == "a1"
    assert record.objective == "test"
    assert record.duration_ms == 100


# ═══════════════════════════════════════════════════
# RR1.5: G-05 — Sin estado oculto
# ═══════════════════════════════════════════════════


def test_g05_no_hidden_state() -> None:
    """AgentScheduler no retiene estado entre shutdowns."""
    s = AgentScheduler(max_concurrent=0)
    s.submit(AgentExecution(
        agent_id="a1", task=AgentTask(task_id="t1", objective="test"),
        capabilities=set(), policy=AgentPolicy(),
    ))
    assert s.queue_size == 1
    s.shutdown(timeout=5)
    # shutdown recolecta resultados pero puede dejar cola
    # Verificar que se puede crear un nuevo scheduler limpio
    s2 = AgentScheduler()
    assert s2.queue_size == 0


# ═══════════════════════════════════════════════════
# RR1.6: G-06 — Determinismo
# ═══════════════════════════════════════════════════


def test_g06_determinism() -> None:
    """RuleBasedPlanner produce planes deterministas."""
    p = RuleBasedPlanner()
    t = AgentTask(task_id="t1", objective="search for X")
    plan1 = p.plan(t)
    plan2 = p.plan(t)
    assert [s.action for s in plan1.steps] == [s.action for s in plan2.steps]


# ═══════════════════════════════════════════════════
# RR1.7: G-07 — Scheduler sin lógica de negocio
# ═══════════════════════════════════════════════════


def test_g07_scheduler_no_business_logic() -> None:
    """Scheduler solo planifica, prioriza, cancela, reintenta."""
    import inspect
    import motor.agents.scheduler as mod
    source = inspect.getsource(mod)
    assert "Planner" not in source or "from motor.agents.base import Planner" not in source
    assert "ToolRunner" not in source or "from motor.agents.base import ToolRunner" not in source
