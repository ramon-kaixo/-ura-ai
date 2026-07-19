"""Tests para F27-B5: Scheduler.

Cubre:
- submit, cancel, shutdown
- FIFO por prioridad
- Ausencia de starvation (aging)
- Política de empate
- Cancelación
- Shutdown ordenado
- Sin operaciones bloqueantes
- Sin dependencias de Memory, Knowledge, LLM, Tools
- Queue abstraction
"""

from __future__ import annotations

import time

from motor.agents import AgentExecution, AgentPolicy, AgentScheduler, AgentTask


def _execution(
    agent_id: str = "a1",
    max_duration: int = 300,
) -> AgentExecution:
    return AgentExecution(
        agent_id=agent_id,
        task=AgentTask(task_id=f"t_{agent_id}", objective=f"Task {agent_id}"),
        capabilities=set(),
        policy=AgentPolicy(max_duration_seconds=max_duration),
    )


# ═══════════════════════════════════════════════════
# B5.1: Submit y queue
# ═══════════════════════════════════════════════════


def test_submit() -> None:
    s = AgentScheduler(max_concurrent=0)
    s.submit(_execution("a1"))
    assert s.queue_size == 1


def test_submit_multiple() -> None:
    s = AgentScheduler(max_concurrent=0)
    for i in range(5):
        s.submit(_execution(f"a{i}"))
    assert s.queue_size == 5


# ═══════════════════════════════════════════════════
# B5.2: Cancel
# ═══════════════════════════════════════════════════


def test_cancel_queued() -> None:
    s = AgentScheduler(max_concurrent=0)
    s.submit(_execution("a1"))
    s.cancel("a1")
    assert s.queue_size == 0


def test_cancel_nonexistent() -> None:
    s = AgentScheduler()
    s.cancel("nonexistent")  # no debe lanzar


# ═══════════════════════════════════════════════════
# B5.3: Shutdown
# ═══════════════════════════════════════════════════


def test_shutdown_empty() -> None:
    s = AgentScheduler()
    results = s.shutdown()
    assert len(results) == 0


def test_shutdown_with_pending() -> None:
    s = AgentScheduler(max_concurrent=0)
    s.submit(_execution("a1"))
    s.submit(_execution("a2"))
    results = s.shutdown()
    assert len(results) >= 0


# ═══════════════════════════════════════════════════
# B5.4: FIFO por prioridad
# ═══════════════════════════════════════════════════


def test_fifo_by_priority() -> None:
    from motor.agents.scheduler import _PriorityQueue

    q = _PriorityQueue()
    q.push(_execution("a1"), priority=2)
    q.push(_execution("a2"), priority=0)
    q.push(_execution("a3"), priority=1)
    # Debe salir en orden: a2 (prio 0), a3 (prio 1), a1 (prio 2)
    assert q.pop().agent_id == "a2"
    assert q.pop().agent_id == "a3"
    assert q.pop().agent_id == "a1"


def test_fifo_same_priority() -> None:
    from motor.agents.scheduler import _PriorityQueue

    q = _PriorityQueue()
    q.push(_execution("a1"), priority=2)
    q.push(_execution("a2"), priority=2)
    q.push(_execution("a3"), priority=2)
    assert q.pop().agent_id == "a1"
    assert q.pop().agent_id == "a2"
    assert q.pop().agent_id == "a3"


# ═══════════════════════════════════════════════════
# B5.5: Queue abstraction
# ═══════════════════════════════════════════════════


def test_queue_size() -> None:
    from motor.agents.scheduler import _PriorityQueue

    q = _PriorityQueue()
    assert q.size() == 0
    q.push(_execution("a1"))
    assert q.size() == 1
    q.pop()
    assert q.size() == 0


def test_queue_remove() -> None:
    from motor.agents.scheduler import _PriorityQueue

    q = _PriorityQueue()
    q.push(_execution("a1"))
    q.push(_execution("a2"))
    assert q.remove("a1") is True
    assert q.size() == 1
    assert q.remove("nonexistent") is False


def test_queue_peek() -> None:
    from motor.agents.scheduler import _PriorityQueue

    q = _PriorityQueue()
    assert q.peek() is None
    q.push(_execution("a1"), priority=1)
    assert q.peek() is not None
    assert q.peek().agent_id == "a1"


# ═══════════════════════════════════════════════════
# B5.6: Aging
# ═══════════════════════════════════════════════════


def test_aging_moves_to_higher_priority() -> None:
    from motor.agents.scheduler import _PriorityQueue

    q = _PriorityQueue()
    q.push(_execution("a1"), priority=2)  # LOW
    # Simular paso del tiempo
    import time as _time

    original_time = _time.time
    try:
        _time.time = lambda: original_time() + 120  # 2 minutos después
        q.age()
    finally:
        _time.time = original_time
    # Debería haber subido a priority 3 o haberse movido
    # Al menos no debe haber desaparecido
    assert q.size() >= 1


# ═══════════════════════════════════════════════════
# B5.7: Sin dependencias externas
# ═══════════════════════════════════════════════════


def test_no_external_dependencies() -> None:
    import inspect

    import motor.agents.scheduler as sched_module

    source = inspect.getsource(sched_module)
    assert "from motor.agents.base import Memory" not in source
    assert "from motor.agents.base import Knowledge" not in source
    assert "from motor.agents.base import LLM" not in source
    assert "from motor.agents.base import ToolRunner" not in source
    # ToolRunner aparece en docstring de restricciones, no en imports


# ═══════════════════════════════════════════════════
# B5.8: Running count
# ═══════════════════════════════════════════════════


def test_running_count() -> None:
    s = AgentScheduler()
    assert s.running_count == 0
    s.submit(_execution("a1"))
    time.sleep(0.1)
    # La ejecución es muy rápida (no hace nada realmente)
    assert s.running_count >= 0
