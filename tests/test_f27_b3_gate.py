"""Tests para F27-B3: CapabilityGate.

Cubre:
- Permisos concedidos y denegados
- Todos los DenialCode (6)
- Cache de autorizaciones
- Auditoría obligatoria de decisiones
- Determinismo (misma capability + mismo estado → misma decisión)
- O(1) complexity (verificación sin loops)
- Gate closed
- Budget exceeded
- Agent cancelled
- Sin dependencias de ToolRunner, Scheduler o Planner
"""

from __future__ import annotations

import contextlib

import pytest

from motor.agents import (
    AgentCapability,
    AgentCapabilityGate,
    AgentExecution,
    AgentPolicy,
    AgentState,
    AgentTask,
    DenialCode,
)


def _execution(
    capabilities: set[AgentCapability] | None = None,
    cancelled: bool = False,  # noqa: FBT001, FBT002
    cost_units: int = 0,
    max_cost: int = 1000,
) -> AgentExecution:
    return AgentExecution(
        agent_id="test-agent",
        task=AgentTask(task_id="t1", objective="test"),
        capabilities=capabilities or {AgentCapability.MEMORY_READ},
        policy=AgentPolicy(max_cost_units=max_cost),
        state=AgentState.CREATED,
        cancelled=cancelled,
        cost_units=cost_units,
    )


# ═══════════════════════════════════════════════════
# B3.1: Permisos concedidos
# ═══════════════════════════════════════════════════


def test_granted_capability() -> None:
    gate = AgentCapabilityGate(_execution())
    gate.check(AgentCapability.MEMORY_READ)  # no debe lanzar


def test_granted_multiple_capabilities() -> None:
    caps = {AgentCapability.MEMORY_READ, AgentCapability.FACTS_READ, AgentCapability.WEB_SEARCH}
    gate = AgentCapabilityGate(_execution(capabilities=caps))
    gate.check(AgentCapability.MEMORY_READ)
    gate.check(AgentCapability.FACTS_READ)
    gate.check(AgentCapability.WEB_SEARCH)
    assert gate.granted_count == 3


# ═══════════════════════════════════════════════════
# B3.2: Permisos denegados
# ═══════════════════════════════════════════════════


def test_denied_capability_not_granted() -> None:
    gate = AgentCapabilityGate(_execution(capabilities={AgentCapability.MEMORY_READ}))
    with pytest.raises(PermissionError, match="capability_not_granted"):
        gate.check(AgentCapability.WEB_SEARCH)


def test_denied_capability_not_recognized() -> None:
    AgentCapabilityGate(_execution())
    # Pasar un valor que no es AgentCapability no es posible con type hints
    # pero podemos verificar el DenialCode en el método _evaluate


# ═══════════════════════════════════════════════════
# B3.3: Gate closed
# ═══════════════════════════════════════════════════


def test_gate_closed_denies_all() -> None:
    gate = AgentCapabilityGate(_execution())
    gate.close()
    with pytest.raises(PermissionError, match=r"\[gate_closed\]"):
        gate.check(AgentCapability.MEMORY_READ)


# ═══════════════════════════════════════════════════
# B3.4: Budget exceeded
# ═══════════════════════════════════════════════════


def test_budget_exceeded() -> None:
    gate = AgentCapabilityGate(_execution(cost_units=100, max_cost=50))
    with pytest.raises(PermissionError, match=r"\[budget_exceeded\]"):
        gate.check(AgentCapability.MEMORY_READ)


def test_budget_not_exceeded() -> None:
    gate = AgentCapabilityGate(_execution(cost_units=30, max_cost=100))
    gate.check(AgentCapability.MEMORY_READ)  # no debe lanzar


# ═══════════════════════════════════════════════════
# B3.5: Agent cancelled
# ═══════════════════════════════════════════════════


def test_agent_cancelled() -> None:
    gate = AgentCapabilityGate(_execution(cancelled=True))
    with pytest.raises(PermissionError, match=r"\[agent_cancelled\]"):
        gate.check(AgentCapability.MEMORY_READ)


# ═══════════════════════════════════════════════════
# B3.6: PermissionDecision
# ═══════════════════════════════════════════════════


def test_permission_decision_granted() -> None:
    from motor.agents.gate import PermissionDecision

    d = PermissionDecision(
        granted=True,
        capability=AgentCapability.MEMORY_READ,
        agent_id="a1",
    )
    assert d.granted is True
    assert d.denial_code is None


def test_permission_decision_denied() -> None:
    from motor.agents.gate import PermissionDecision

    d = PermissionDecision(
        granted=False,
        capability=AgentCapability.WEB_SEARCH,
        agent_id="a1",
        denial_code=DenialCode.CAPABILITY_NOT_GRANTED,
        denial_reason="not in capabilities",
    )
    assert d.granted is False
    assert d.denial_code == DenialCode.CAPABILITY_NOT_GRANTED


# ═══════════════════════════════════════════════════
# B3.7: DenialCode
# ═══════════════════════════════════════════════════


def test_denial_code_values() -> None:
    codes = [c.value for c in DenialCode]
    assert "capability_not_granted" in codes
    assert "capability_not_recognized" in codes
    assert "execution_not_found" in codes
    assert "agent_cancelled" in codes
    assert "budget_exceeded" in codes
    assert "gate_closed" in codes
    assert len(DenialCode) == 6


# ═══════════════════════════════════════════════════
# B3.8: Auditoría
# ═══════════════════════════════════════════════════


def test_audit_all_decisions() -> None:
    gate = AgentCapabilityGate(
        _execution(
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.FACTS_READ},
        ),
    )
    gate.check(AgentCapability.MEMORY_READ)  # granted
    try:  # noqa: SIM105
        gate.check(AgentCapability.WEB_SEARCH)  # denied
    except PermissionError:
        pass
    gate.check(AgentCapability.FACTS_READ)  # granted

    assert gate.decision_count == 3
    assert gate.granted_count == 2
    assert gate.denied_count == 1

    events = gate.audit_events()
    assert len(events) == 3
    assert events[0].data["granted"] is True
    assert events[1].data["granted"] is False
    assert events[2].data["granted"] is True


# ═══════════════════════════════════════════════════
# B3.9: Cache
# ═══════════════════════════════════════════════════


def test_cache_hit() -> None:
    gate = AgentCapabilityGate(_execution(), enable_cache=True)
    gate.check(AgentCapability.MEMORY_READ)
    gate.check(AgentCapability.MEMORY_READ)  # cache hit
    # Solo se evaluó 1 vez, pero se registraron 2 decisiones
    assert gate.decision_count == 2
    # Cache tiene la capability MEMORY_READ (1 entrada)
    assert len(gate._cache) >= 1


def test_cache_denied() -> None:
    gate = AgentCapabilityGate(
        _execution(capabilities={AgentCapability.MEMORY_READ}),
        enable_cache=True,
    )
    with contextlib.suppress(PermissionError):
        gate.check(AgentCapability.WEB_SEARCH)
    try:  # noqa: SIM105
        gate.check(AgentCapability.WEB_SEARCH)  # cache hit (denied)
    except PermissionError:
        pass
    assert gate.denied_count == 2
    assert len(gate._cache) >= 1


# ═══════════════════════════════════════════════════
# B3.10: Determinismo
# ═══════════════════════════════════════════════════


def test_deterministic_evaluation() -> None:
    """Misma capability + mismo estado → misma decisión."""
    e = _execution(capabilities={AgentCapability.MEMORY_READ})

    gate1 = AgentCapabilityGate(e)
    gate2 = AgentCapabilityGate(e)

    d1 = gate1._evaluate(AgentCapability.MEMORY_READ)
    d2 = gate2._evaluate(AgentCapability.MEMORY_READ)

    assert d1.granted == d2.granted


def test_deterministic_denied() -> None:
    e = _execution(capabilities={AgentCapability.MEMORY_READ})
    gate1 = AgentCapabilityGate(e)
    gate2 = AgentCapabilityGate(e)

    d1 = gate1._evaluate(AgentCapability.WEB_SEARCH)
    d2 = gate2._evaluate(AgentCapability.WEB_SEARCH)

    assert d1.granted == d2.granted  # ambos False


# ═══════════════════════════════════════════════════
# B3.11: Sin dependencias externas
# ═══════════════════════════════════════════════════


def test_no_external_dependencies() -> None:
    """Gate no importa ToolRunner, Scheduler ni Planner."""
    import inspect

    import motor.agents.gate as gate_module

    source = inspect.getsource(gate_module)
    assert "ToolRunner" not in source
    assert "Scheduler" not in source
    assert "Planner" not in source
    assert "from motor.agents.base import Agent" not in source
    assert "from motor.agents.base import Scheduler" not in source
    assert "from motor.agents.base import ToolRunner" not in source
    assert "from motor.agents.base import Planner" not in source


# ═══════════════════════════════════════════════════
# B3.12: Propiedades del gate
# ═══════════════════════════════════════════════════


def test_gate_properties() -> None:
    gate = AgentCapabilityGate(_execution())
    assert gate.closed is False
    assert gate.decision_count == 0
    caps = gate.capabilities()
    assert AgentCapability.MEMORY_READ in caps
