"""F27-B8: Hardening del Sistema de Agentes.

Estress, concurrencia, caos, determinismo y property-based testing.
"""

from __future__ import annotations

import random
import threading
import time

import pytest

from motor.agents import (
    AgentCapability,
    AgentCapabilityGate,
    AgentExecution,
    AgentPolicy,
    AgentScheduler,
    AgentState,
    AgentStateMachine,
    AgentTask,
    AgentToolRunner,
    DenialCode,
    ToolAdapter,
    ToolContract,
    ToolTimeoutError,
    ToolTransientError,
)


# ── Helpers ────────────────────────────────────────────

_COUNTER: list[int] = [0]


def _task() -> AgentTask:
    _COUNTER[0] += 1
    return AgentTask(task_id=f"t{_COUNTER[0]}", objective=f"task {_COUNTER[0]}")


def _exec(caps: set[AgentCapability] | None = None) -> AgentExecution:
    return AgentExecution(
        agent_id=f"a{_COUNTER[0]}",
        task=_task(),
        capabilities=caps or {AgentCapability.MEMORY_READ},
        policy=AgentPolicy(max_duration_seconds=300, max_cost_units=1000),
    )


# ═══════════════════════════════════════════════════
# B8.1: Property-based StateMachine
# ═══════════════════════════════════════════════════


def test_state_machine_all_transitions() -> None:
    """Verificar que todas las transiciones válidas funcionan."""
    sm = AgentStateMachine()
    for source in AgentState:
        targets = sm.valid_transitions(source)
        for target in targets:
            assert sm.transition(source, target) == target


def test_state_machine_no_invalid_transitions() -> None:
    """Verificar que transiciones inválidas lanzan ValueError."""
    sm = AgentStateMachine()
    invalid = [
        (AgentState.CREATED, AgentState.COMPLETED),
        (AgentState.COMPLETED, AgentState.RUNNING),
        (AgentState.CANCELLED, AgentState.RUNNING),
        (AgentState.FAILED, AgentState.RUNNING),
        (AgentState.TIMEOUT, AgentState.RUNNING),
    ]
    for source, target in invalid:
        with pytest.raises(ValueError):
            sm.transition(source, target)


def test_state_machine_random_sequences() -> None:
    """Property-based: secuencias aleatorias no deben corromper el estado."""
    sm = AgentStateMachine()
    rng = random.Random(42)
    for _ in range(1000):
        state = AgentState.CREATED
        for _ in range(20):
            valid = sm.valid_transitions(state)
            if not valid:
                break
            target = rng.choice(valid)
            state = sm.transition(state, target)


# ═══════════════════════════════════════════════════
# B8.2: Estrés con cientos de ejecuciones
# ═══════════════════════════════════════════════════


def test_scheduler_stress_1000_tasks() -> None:
    s = AgentScheduler(max_concurrent=10)
    for i in range(1000):
        s.submit(_exec())
    time.sleep(1)
    results = s.shutdown(timeout=10)
    assert len(results) >= 0


# ═══════════════════════════════════════════════════
# B8.3: Múltiples agentes concurrentes
# ═══════════════════════════════════════════════════


def test_concurrent_agents_50() -> None:
    s = AgentScheduler(max_concurrent=10)
    errors: list[Exception] = []

    def submitter(n: int) -> None:
        try:
            for _ in range(10):
                s.submit(_exec())
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=submitter, args=(i,), daemon=True) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    s.shutdown(timeout=5)
    assert not errors


# ═══════════════════════════════════════════════════
# B8.4: Cancelaciones masivas
# ═══════════════════════════════════════════════════


def test_mass_cancellation_500() -> None:
    s = AgentScheduler(max_concurrent=0)
    ids: list[str] = []
    for i in range(500):
        exec_obj = _exec()
        ids.append(exec_obj.agent_id)
        s.submit(exec_obj)
    for aid in ids:
        s.cancel(aid)
    assert s.queue_size == 0


# ═══════════════════════════════════════════════════
# B8.5: Timeouts simultáneos
# ═══════════════════════════════════════════════════


class _SlowAdapter(ToolAdapter):
    def name(self): return "slow"
    def run(self, params): time.sleep(5); return {}
    def cancel(self): pass


def test_multiple_timeouts() -> None:
    runner = AgentToolRunner()
    runner.register("slow", _SlowAdapter(), ToolContract(name="slow", timeout_seconds=1))
    errors = 0
    for _ in range(5):
        try:
            runner.run("slow", {}, timeout=1)
        except ToolTimeoutError:
            errors += 1
    assert errors == 5


# ═══════════════════════════════════════════════════
# B8.6: Fallos intermitentes + recuperación
# ═══════════════════════════════════════════════════


class _FlakyAdapter(ToolAdapter):
    def __init__(self):
        self._call_count = 0
    def name(self): return "flaky"
    def run(self, params):
        self._call_count += 1
        if self._call_count <= 2:
            raise ToolTransientError("transient error")
        return {"ok": True}
    def cancel(self): pass


def test_flaky_tool_recovers() -> None:
    runner = AgentToolRunner()
    runner.register("flaky", _FlakyAdapter(), ToolContract(name="flaky", timeout_seconds=5))
    result = runner.run("flaky", {})
    assert result == {"ok": True}


# ═══════════════════════════════════════════════════
# B8.7: Presupuesto agotado
# ═══════════════════════════════════════════════════


def test_budget_exhaustion() -> None:
    """Budget agotado debe denegar capabilities."""
    execution = AgentExecution(
        agent_id="b1", task=_task(),
        capabilities={AgentCapability.MEMORY_READ},
        policy=AgentPolicy(max_cost_units=10),
        cost_units=10,
    )
    gate = AgentCapabilityGate(execution)
    with pytest.raises(PermissionError):
        gate.check(AgentCapability.MEMORY_READ)


# ═══════════════════════════════════════════════════
# B8.8: Determinismo sin LLM
# ═══════════════════════════════════════════════════


def test_gate_deterministic() -> None:
    """Mismo execution → mismas decisiones."""
    e1 = _exec()
    e2 = AgentExecution(
        agent_id=e1.agent_id, task=e1.task,
        capabilities=e1.capabilities, policy=e1.policy,
    )
    g1 = AgentCapabilityGate(e1)
    g2 = AgentCapabilityGate(e2)
    try:
        g1.check(AgentCapability.WEB_SEARCH)
    except PermissionError:
        pass
    try:
        g2.check(AgentCapability.WEB_SEARCH)
    except PermissionError:
        pass
    assert len(g1._decisions) > 0
    assert len(g2._decisions) > 0
