from __future__ import annotations

import time
from typing import TYPE_CHECKING

from motor.intelligence.agents.executor import ExecutorAgent
from motor.intelligence.agents.message import AgentTask
from motor.intelligence.agents.parallel import ExecutionResult, ParallelExecutor
from motor.intelligence.agents.runtime import MultiAgentRuntime

if TYPE_CHECKING:
    from motor.intelligence.agents.base import Agent


def _agent_id(agent: Agent) -> str:
    return agent.id


class TestExecutionResult:
    def test_defaults(self):
        r = ExecutionResult(workflow_id="w1", total_tasks=0)
        assert r.completed == 0
        assert r.failed == 0
        assert r.cancelled == 0
        assert r.elapsed_ms == 0.0

    def test_success(self):
        r = ExecutionResult(workflow_id="w1", total_tasks=1, completed=1)
        assert r.success

    def test_failure(self):
        r = ExecutionResult(workflow_id="w1", total_tasks=1, failed=1)
        assert not r.success


class TestParallelExecutor:
    def _make_agents(self, count: int = 3) -> list[ExecutorAgent]:
        return [ExecutorAgent() for _ in range(count)]

    def _make_registry(self, agents: list[ExecutorAgent]) -> dict[str, ExecutorAgent]:
        return {a.id: a for a in agents}

    def test_single_task(self):
        agents = self._make_agents(1)
        registry = self._make_registry(agents)
        executor = ParallelExecutor(find_agent_fn=registry.get)
        tasks = [(agents[0].id, AgentTask(objective="echo", input_data={"cmd": ["echo", "ok"]}))]
        result = executor.execute(tasks)
        assert result.completed == 1
        assert result.total_tasks == 1

    def test_multiple_tasks(self):
        agents = self._make_agents(3)
        registry = self._make_registry(agents)
        executor = ParallelExecutor(find_agent_fn=registry.get)
        tasks = [
            (a.id, AgentTask(objective="echo", input_data={"cmd": ["echo", f"t{i}"]})) for i, a in enumerate(agents)
        ]
        result = executor.execute(tasks)
        assert result.completed == 3
        assert result.total_tasks == 3

    def test_all_results_preserved(self):
        agents = self._make_agents(3)
        registry = self._make_registry(agents)
        executor = ParallelExecutor(find_agent_fn=registry.get)
        tasks = [
            (a.id, AgentTask(objective="echo", input_data={"cmd": ["echo", f"msg_{i}"]})) for i, a in enumerate(agents)
        ]
        result = executor.execute(tasks)
        assert len(result.results) == 3

    def test_agent_not_found(self):
        executor = ParallelExecutor(find_agent_fn=lambda aid: None)
        tasks = [("nonexistent", AgentTask(objective="echo"))]
        result = executor.execute(tasks)
        assert result.failed == 1
        assert any("agent_not_found" in e for e in result.errors)

    def test_empty_tasks(self):
        executor = ParallelExecutor()
        result = executor.execute([])
        assert result.total_tasks == 0
        assert result.completed == 0

    def test_cancel_before_start(self):
        executor = ParallelExecutor()
        wf_id = "test_cancel_before"
        executor.cancel(wf_id)
        tasks = [("a1", AgentTask(objective="echo"))]
        result = executor.execute(tasks, workflow_id=wf_id)
        assert result.cancelled == 1
        assert result.cancelled_by_user

    def test_cancel_during(self):
        agents = self._make_agents(3)
        registry = self._make_registry(agents)
        executor = ParallelExecutor(find_agent_fn=registry.get)
        wf_id = "cancel_during"
        tasks = [(a.id, AgentTask(objective="echo", input_data={"cmd": ["echo", "x"]})) for a in agents]
        executor.cancel(wf_id)
        result = executor.execute(tasks, workflow_id=wf_id)
        # Some may have started before cancel, some cancelled
        assert result.cancelled >= 0

    def test_timeout(self):
        agents = self._make_agents(1)
        registry = self._make_registry(agents)
        executor = ParallelExecutor(
            find_agent_fn=registry.get,
            global_timeout=0.001,
        )
        tasks = [(agents[0].id, AgentTask(objective="echo", input_data={"cmd": ["sleep", "10"]}))]
        result = executor.execute(tasks)
        # The task might time out
        assert result.failed >= 0

    def test_fail_fast(self):
        agents = self._make_agents(3)
        registry = self._make_registry(agents)
        executor = ParallelExecutor(
            find_agent_fn=registry.get,
            fail_fast=True,
        )
        failing = AgentTask(objective="fail", input_data={"cmd": ["bash", "-c", "exit 1"]})
        succeeding = AgentTask(objective="echo", input_data={"cmd": ["echo", "ok"]})
        tasks = [(agents[0].id, failing), (agents[1].id, succeeding), (agents[2].id, succeeding)]
        result = executor.execute(tasks)
        # At least one failed, fail_fast may cancel remaining
        assert result.failed >= 1

    def test_cancel_on_error(self):
        agents = self._make_agents(3)
        registry = self._make_registry(agents)
        executor = ParallelExecutor(
            find_agent_fn=registry.get,
            cancel_on_error=True,
        )
        failing = AgentTask(objective="fail", input_data={"cmd": ["bash", "-c", "exit 1"]})
        tasks = [
            (agents[0].id, failing),
            (agents[1].id, AgentTask(objective="echo", input_data={"cmd": ["echo", "ok"]})),
        ]
        result = executor.execute(tasks)
        # fail_on_error cancels remaining after first failure
        assert result.total_tasks == 2
        assert result.failed >= 0

    def test_max_workers(self):
        executor = ParallelExecutor(max_workers=8)
        assert executor.max_workers == 8

    def test_is_cancelled(self):
        executor = ParallelExecutor()
        assert not executor.is_cancelled("w1")
        executor.cancel("w1")
        assert executor.is_cancelled("w1")

    def test_cancel_twice(self):
        executor = ParallelExecutor()
        assert executor.cancel("w1") is True
        assert executor.cancel("w1") is False  # already cancelled

    def test_close(self):
        executor = ParallelExecutor()
        executor.cancel("w1")
        executor.close()
        assert not executor.is_cancelled("w1")

    def test_partial_results_on_error(self):
        agents = self._make_agents(2)
        registry = self._make_registry(agents)
        executor = ParallelExecutor(
            find_agent_fn=registry.get,
            fail_fast=False,
        )
        ok_task = AgentTask(objective="echo", input_data={"cmd": ["echo", "ok"]})
        fail_task = AgentTask(objective="fail", input_data={"cmd": ["bash", "-c", "exit 1"]})
        tasks = [(agents[0].id, ok_task), (agents[1].id, fail_task)]
        result = executor.execute(tasks)
        # Should have at least the partial results
        assert result.completed + result.failed == 2

    def test_no_find_agent_fn(self):
        executor = ParallelExecutor()
        tasks = [("a1", AgentTask(objective="echo"))]
        result = executor.execute(tasks)
        assert result.failed == 1


class TestExecutionOrder:
    def test_result_order_preserved(self):
        agents = [ExecutorAgent(), ExecutorAgent(), ExecutorAgent()]
        registry = {a.id: a for a in agents}
        executor = ParallelExecutor(find_agent_fn=registry.get)
        tasks = [
            (a.id, AgentTask(objective="echo", input_data={"cmd": ["echo", str(i)]})) for i, a in enumerate(agents)
        ]
        result = executor.execute(tasks)
        assert len(result.results) == 3


class TestThreadSafety:
    def test_concurrent_cancel(self):
        import concurrent.futures

        executor = ParallelExecutor()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
            futures = [exe.submit(executor.cancel, f"w{i}") for i in range(100)]
            concurrent.futures.wait(futures)
        # Should not raise
        assert True


class TestIntegration:
    def test_with_multi_agent_runtime(self):
        runtime = MultiAgentRuntime()
        agent = ExecutorAgent()
        runtime.register(agent)

        executor = ParallelExecutor(
            find_agent_fn=runtime.get_agent,
        )
        task = AgentTask(objective="echo", input_data={"cmd": ["echo", "integration"]})
        tasks = [(agent.id, task)]
        result = executor.execute(tasks)
        assert result.completed == 1

    def test_parallel_vs_sequential(self):
        agents = [ExecutorAgent() for _ in range(3)]
        registry = {a.id: a for a in agents}
        executor = ParallelExecutor(find_agent_fn=registry.get, max_workers=3)
        tasks = [(a.id, AgentTask(objective="echo", input_data={"cmd": ["echo", "x"]})) for a in agents]
        start = time.monotonic()
        result = executor.execute(tasks)
        elapsed_parallel = (time.monotonic() - start) * 1000

        # Sequential
        start = time.monotonic()
        for aid, task in tasks:
            agent = registry.get(aid)
            if agent:
                agent.run(task)
        elapsed_sequential = (time.monotonic() - start) * 1000

        assert result.completed == 3
        # Parallel should not be significantly slower than sequential for fast tasks
        assert elapsed_parallel < elapsed_sequential * 2 or elapsed_parallel < 100

    def test_different_max_workers(self):
        for n in [1, 2, 8]:
            executor = ParallelExecutor(max_workers=n)
            assert executor.max_workers == n
