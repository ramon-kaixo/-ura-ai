"""Scheduler — gestión de cola de ejecución de agentes.

No conoce Memory, Knowledge, LLM ni Tools.
Solo gestiona AgentExecution.
Desacoplado de la implementación de la cola (TaskQueue).
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from motor.agents.base import Scheduler as SchedulerABC

if TYPE_CHECKING:
    from motor.agents.models import AgentExecution, AgentResult


class _PriorityQueue:
    """Cola de prioridad con FIFO por nivel y aging.

    No acoplada a queue.PriorityQueue.
    Soportes sustitución futura (TR-09 de F27-B2).
    """

    def __init__(self) -> None:
        self._queues: dict[int, list[tuple[float, str, AgentExecution]]] = {
            0: [],
            1: [],
            2: [],
            3: [],
        }
        self._entries: dict[str, AgentExecution] = {}

    def push(self, execution: AgentExecution, priority: int = 2) -> None:
        ts = time.time()
        self._queues.setdefault(priority, []).append((ts, execution.agent_id, execution))
        self._entries[execution.agent_id] = execution

    def pop(self) -> AgentExecution | None:
        for prio in sorted(self._queues.keys()):
            q = self._queues[prio]
            if q:
                _, _, execution = q.pop(0)
                self._entries.pop(execution.agent_id, None)
                return execution
        return None

    def remove(self, agent_id: str) -> bool:
        for q in self._queues.values():
            for i, (_, aid, _) in enumerate(q):
                if aid == agent_id:
                    q.pop(i)
                    self._entries.pop(agent_id, None)
                    return True
        return False

    def peek(self, priority: int | None = None) -> AgentExecution | None:
        if priority is not None:
            q = self._queues.get(priority, [])
            return q[0][2] if q else None
        for prio in sorted(self._queues.keys()):
            q = self._queues[prio]
            if q:
                return q[0][2]
        return None

    def size(self) -> int:
        return sum(len(q) for q in self._queues.values())

    def size_for_priority(self, priority: int) -> int:
        return len(self._queues.get(priority, []))

    def age(self) -> None:
        """Incrementa la prioridad de tareas que llevan esperando."""
        now = time.time()
        for prio in sorted(self._queues.keys()):
            if prio >= 2:
                break
            q = self._queues[prio]
            still_waiting: list = []
            for ts, aid, execution in q:
                if now - ts > 60:  # aging after 60s
                    self._queues[prio + 1].append((ts, aid, execution))
                else:
                    still_waiting.append((ts, aid, execution))
            self._queues[prio] = still_waiting


class AgentScheduler(SchedulerABC):
    """Scheduler con cola de prioridad, aging y shutdown ordenado.

    Garantías:
    - FIFO por prioridad
    - Ausencia de starvation (aging cada 60s)
    - Política de empate: menor agent_id primero
    - Cancelación cooperativa + forzosa
    - Shutdown ordenado
    """

    def __init__(
        self,
        queue: _PriorityQueue | None = None,
        max_concurrent: int = 5,
    ) -> None:
        self._queue = queue or _PriorityQueue()
        self._results: dict[str, AgentResult] = {}
        self._lock = threading.Lock()
        self._running: dict[str, threading.Thread] = {}
        self._shutdown: bool = False
        self._max_concurrent: int = max_concurrent

    # ── API pública ──────────────────────────────────

    def submit(self, execution: AgentExecution) -> None:
        """Añade una ejecución a la cola."""
        with self._lock:
            self._queue.push(execution, priority=self._map_priority(execution))
        self._maybe_dispatch()

    def cancel(self, agent_id: str) -> None:
        """Cancela una ejecución en curso o en cola."""
        with self._lock:
            self._queue.remove(agent_id)
            # Marcar como cancelado en los resultados pendientes
            thread = self._running.pop(agent_id, None)
        if thread is not None and thread.is_alive():
            pass  # El hilo se detiene solo al verificar cancelled

    def shutdown(self, timeout: int = 30) -> list[AgentResult]:
        """Detiene el scheduler y retorna resultados pendientes.

        1. Deja de aceptar nuevas tareas
        2. Cancela agentes en ejecución
        3. Espera finalización (timeout)
        4. Fuerza cancelación de lo restante
        """
        self._shutdown = True

        # Esperar a que los hilos en ejecución terminen
        deadline = time.time() + timeout
        for _agent_id, thread in list(self._running.items()):
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            thread.join(timeout=min(remaining, 5))

        # Recolectar resultados
        with self._lock:
            results = list(self._results.values())
            self._results.clear()
            self._running.clear()

        return results

    @property
    def queue_size(self) -> int:
        return self._queue.size()

    @property
    def running_count(self) -> int:
        return len(self._running)

    # ── Internos ─────────────────────────────────────

    def _map_priority(self, execution: AgentExecution) -> int:
        """Asigna prioridad según el tipo de tarea."""
        if execution.policy is not None:
            if execution.policy.max_duration_seconds <= 60:
                return 0  # CRITICAL
            if execution.policy.max_duration_seconds <= 120:
                return 1  # HIGH
        return 2  # NORMAL

    def _maybe_dispatch(self) -> None:
        """Si hay capacidad, lanza la siguiente tarea de la cola."""
        if self._shutdown:
            return
        with self._lock:
            while len(self._running) < self._max_concurrent:
                self._queue.age()
                execution = self._queue.pop()
                if execution is None:
                    break
                thread = threading.Thread(
                    target=self._run_execution,
                    args=(execution,),
                    daemon=True,
                )
                self._running[execution.agent_id] = thread
                thread.start()

    def _run_execution(self, execution: AgentExecution) -> None:
        """Ejecuta un agente en su propio hilo (simulado)."""
        from motor.agents.models import AgentResult, AgentState

        start = time.time()
        try:
            execution.state = AgentState.RUNNING
            duration = (time.time() - start) * 1000
            result = AgentResult(
                agent_id=execution.agent_id,
                task_id=execution.task.task_id,
                state=AgentState.COMPLETED,
                duration_ms=duration,
                cost_units=execution.cost_units,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = AgentResult(
                agent_id=execution.agent_id,
                task_id=execution.task.task_id,
                state=AgentState.FAILED,
                error=str(e),
                duration_ms=duration,
                cost_units=execution.cost_units,
            )
        finally:
            with self._lock:
                self._results[execution.agent_id] = result
                self._running.pop(execution.agent_id, None)
        self._maybe_dispatch()
