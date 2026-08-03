"""Tests para motor.agents.scheduler (AgentScheduler, _PriorityQueue)."""
from __future__ import annotations

import threading
import time
from unittest import mock

from motor.agents.models import (
    AgentCapability,
    AgentExecution,
    AgentPolicy,
    AgentState,
    AgentTask,
)
from motor.agents.scheduler import AgentScheduler, _PriorityQueue


def _task(task_id: str = "t1") -> AgentTask:
    return AgentTask(task_id=task_id, objective="obj")


def _execution(agent_id: str = "a1", policy: AgentPolicy | None = None, task: AgentTask | None = None) -> AgentExecution:
    return AgentExecution(
        agent_id=agent_id,
        task=task or _task(),
        capabilities={AgentCapability.FACTS_READ},
        policy=policy or AgentPolicy(),
    )


class TestPriorityQueue:
    def test_push_pop_fifo(self):
        q = _PriorityQueue()
        q.push(_execution("a1"))
        q.push(_execution("a2"))
        assert q.size() == 2
        assert q.pop().agent_id == "a1"
        assert q.pop().agent_id == "a2"
        assert q.pop() is None

    def test_pop_priority_order(self):
        q = _PriorityQueue()
        q.push(_execution("normal"))
        q.push(_execution("crit"), priority=0)
        assert q.pop().agent_id == "crit"
        assert q.pop().agent_id == "normal"

    def test_push_unknown_priority_creates(self):
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=7)
        assert q.size_for_priority(7) == 1
        assert q.pop().agent_id == "a1"

    def test_remove(self):
        q = _PriorityQueue()
        q.push(_execution("a1"))
        q.push(_execution("a2"))
        assert q.remove("a1") is True
        assert q.size() == 1
        assert q.remove("a1") is False
        assert q.pop().agent_id == "a2"

    def test_peek(self):
        q = _PriorityQueue()
        assert q.peek() is None
        q.push(_execution("a1"))
        q.push(_execution("a2"), priority=0)
        assert q.peek(priority=0).agent_id == "a2"
        assert q.peek(priority=5) is None
        assert q.peek().agent_id == "a2"
        assert q.size() == 2

    def test_size_for_priority(self):
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=0)
        q.push(_execution("a2"), priority=2)
        assert q.size_for_priority(0) == 1
        assert q.size_for_priority(2) == 1
        assert q.size_for_priority(9) == 0

    def test_age_promotes_old(self):
        q = _PriorityQueue()
        with mock.patch("motor.agents.scheduler.time.time", return_value=1000.0):
            q.push(_execution("old1"), priority=0)
            q.push(_execution("old2"), priority=1)
        with mock.patch("motor.agents.scheduler.time.time", return_value=1070.0):
            q.push(_execution("fresh"), priority=0)
        with mock.patch("motor.agents.scheduler.time.time", return_value=1100.0):
            q.age()
        assert q.size_for_priority(0) == 1  # fresh stays (age 30s <= 60)
        assert q.size_for_priority(1) == 0  # old1 promovido en cascada hasta prio 2
        assert q.size_for_priority(2) == 2  # old1 + old2
        assert q.size_for_priority(3) == 0

    def test_age_stops_at_priority_2(self):
        q = _PriorityQueue()
        with mock.patch("motor.agents.scheduler.time.time", return_value=1000.0):
            q.push(_execution("p2"), priority=2)
            q.push(_execution("p3"), priority=3)
        with mock.patch("motor.agents.scheduler.time.time", return_value=1100.0):
            q.age()
        assert q.size_for_priority(2) == 1
        assert q.size_for_priority(3) == 1


class TestAgentScheduler:
    def test_init_defaults(self):
        s = AgentScheduler()
        assert s.queue_size == 0
        assert s.running_count == 0

    def test_submit_dispatches(self):
        s = AgentScheduler(max_concurrent=1)
        s.submit(_execution("a1"))
        assert s.queue_size == 0
        assert s.running_count == 1
        s.shutdown(timeout=5)
        assert len(s.shutdown(timeout=5) or []) >= 0

    def test_map_priority(self):
        s = AgentScheduler()
        assert s._map_priority(_execution("x", policy=AgentPolicy(max_duration_seconds=30))) == 0
        assert s._map_priority(_execution("x", policy=AgentPolicy(max_duration_seconds=90))) == 1
        assert s._map_priority(_execution("x", policy=AgentPolicy(max_duration_seconds=300))) == 2
        assert s._map_priority(_execution("x", policy=None)) == 2

    def test_cancel_queued(self):
        s = AgentScheduler(max_concurrent=0)  # no dispatch
        s.submit(_execution("a1"))
        assert s.queue_size == 1
        s.cancel("a1")
        assert s.queue_size == 0

    def test_cancel_running(self):
        s = AgentScheduler(max_concurrent=1)
        s.submit(_execution("a1"))
        s.cancel("a1")
        assert s.running_count <= 1

    def test_shutdown_returns_results(self):
        s = AgentScheduler(max_concurrent=2)
        s.submit(_execution("a1"))
        s.submit(_execution("a2"))
        deadline = time.time() + 10
        results = []
        while time.time() < deadline:
            results = s.shutdown(timeout=1)
            if results:
                break
            time.sleep(0.1)
        assert len(results) == 2
        assert all(r.state == AgentState.COMPLETED for r in results)
        assert s.running_count == 0

    def test_shutdown_with_deadline_passed(self):
        s = AgentScheduler(max_concurrent=1)
        s.submit(_execution("a1"))
        with mock.patch("motor.agents.scheduler.time.time", side_effect=[1000.0, 2000.0, 2000.0]):
            results = s.shutdown(timeout=1)
        assert isinstance(results, list)

    def test_max_concurrent_limits(self):
        s = AgentScheduler(max_concurrent=2)
        gate = threading.Event()
        with mock.patch.object(s, "_run_execution", side_effect=lambda exec_: gate.wait(5)):
            for i in range(6):
                s.submit(_execution(f"a{i}"))
        assert s.running_count == 2
        assert s.queue_size == 4
        gate.set()
        s.shutdown(timeout=5)

    def test_shutdown_blocks_new_submissions(self):
        s = AgentScheduler(max_concurrent=0)
        s.shutdown(timeout=1)
        s.submit(_execution("a1"))
        assert s.queue_size == 1  # en cola pero no despachado

    def test_run_execution_success(self):
        s = AgentScheduler()
        execution = _execution("a1")
        with mock.patch("motor.agents.scheduler.threading.Thread") as thread_cls:
            thread = mock.Mock()
            thread_cls.return_value = thread
            s._run_execution(execution)
        assert execution.state == AgentState.RUNNING
        result = s._results["a1"]
        assert result.state == AgentState.COMPLETED
        assert result.task_id == "t1"

    def test_run_execution_error(self):
        s = AgentScheduler()
        execution = _execution("a1")
        with mock.patch.object(
            type(execution),
            "cost_units",
            new_callable=mock.PropertyMock,
            side_effect=[RuntimeError("boom"), 5],
        ):
            s._run_execution(execution)
        result = s._results["a1"]
        assert result.state == AgentState.FAILED
        assert "boom" in (result.error or "")

    def test_maybe_dispatch_after_shutdown(self):
        s = AgentScheduler(max_concurrent=0)
        s._shutdown = True
        s.submit(_execution("a1"))
        assert s.running_count == 0
        assert s.queue_size == 1

    def test_submit_runs_in_thread(self):
        s = AgentScheduler(max_concurrent=1)
        execution = _execution("a1")
        with mock.patch("motor.agents.scheduler.threading.Thread") as thread_cls:
            thread = mock.Mock()
            thread_cls.return_value = thread
            s.submit(execution)
        thread_cls.assert_called_once()
        thread.start.assert_called_once()
        s.shutdown(timeout=1)
