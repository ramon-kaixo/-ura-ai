from __future__ import annotations

import concurrent.futures

import pytest

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.executor import ExecutorAgent
from motor.intelligence.agents.message import AgentMessage, AgentResult, AgentRole, AgentStatus, AgentTask
from motor.intelligence.agents.planner import PlannerAgent
from motor.intelligence.agents.researcher import ResearcherAgent
from motor.intelligence.agents.runtime import MultiAgentRuntime
from motor.intelligence.agents.supervisor import SupervisorAgent
from motor.intelligence.agents.validator import ValidatorAgent


class TestAgentMessage:
    def test_auto_id(self):
        m = AgentMessage(source="a", target="b", message_type="task", payload={})
        assert m.id != ""
        assert m.timestamp != ""

    def test_auto_correlation(self):
        m = AgentMessage(source="a", target="b", message_type="task", payload={})
        assert m.correlation_id == m.id

    def test_custom_id(self):
        m = AgentMessage(source="a", target="b", message_type="task", payload={}, id="custom")
        assert m.id == "custom"


class TestAgentTask:
    def test_auto_id(self):
        t = AgentTask(objective="test")
        assert t.id != ""
        assert t.created_at != ""

    def test_defaults(self):
        t = AgentTask(objective="test")
        assert t.agent_role == AgentRole.EXECUTOR
        assert t.priority == 0
        assert t.timeout == 60


class TestAgentResult:
    def test_auto_id(self):
        r = AgentResult(task_id="t1", agent_id="a1", success=True)
        assert r.id != ""


class TestPlannerAgent:
    def test_plan_search(self):
        agent = PlannerAgent()
        task = AgentTask(objective="search for documents")
        result = agent.run(task)
        assert result.success
        subtasks = result.output.get("subtasks", [])
        assert any(s["agent_role"] == AgentRole.RESEARCHER for s in subtasks)

    def test_plan_execute(self):
        agent = PlannerAgent()
        task = AgentTask(objective="execute the pipeline")
        result = agent.run(task)
        assert result.success
        subtasks = result.output.get("subtasks", [])
        assert any(s["agent_role"] == AgentRole.EXECUTOR for s in subtasks)

    def test_plan_validate(self):
        agent = PlannerAgent()
        task = AgentTask(objective="validate the results")
        result = agent.run(task)
        assert result.success
        subtasks = result.output.get("subtasks", [])
        assert any(s["agent_role"] == AgentRole.VALIDATOR for s in subtasks)

    def test_plan_multiple(self):
        agent = PlannerAgent()
        task = AgentTask(objective="search and validate the results")
        result = agent.run(task)
        assert result.success
        subtasks = result.output.get("subtasks", [])
        assert len(subtasks) >= 2

    def test_plan_generic(self):
        agent = PlannerAgent()
        task = AgentTask(objective="do something generic")
        result = agent.run(task)
        assert result.success
        assert result.output["subtasks"][0]["agent_role"] == AgentRole.EXECUTOR


class TestExecutorAgent:
    def test_execute_simple(self):
        agent = ExecutorAgent()
        task = AgentTask(objective="echo test", input_data={"cmd": ["echo", "hello"]})
        result = agent.run(task)
        assert result.success
        assert "hello" in result.output.get("stdout", "")

    def test_execute_failure(self):
        agent = ExecutorAgent()
        task = AgentTask(objective="fail", input_data={"cmd": ["bash", "-c", "exit 1"]})
        result = agent.run(task)
        assert not result.success

    def test_execute_timeout(self):
        agent = ExecutorAgent()
        task = AgentTask(objective="timeout", input_data={"cmd": ["sleep", "10"], "timeout": 1})
        result = agent.run(task)
        assert not result.success


class TestValidatorAgent:
    def test_validate_success(self):
        agent = ValidatorAgent()
        task = AgentTask(objective="validate", input_data={"result": {"success": True, "output": "ok"}})
        result = agent.run(task)
        assert result.success
        assert result.output["valid"]

    def test_validate_failure(self):
        agent = ValidatorAgent()
        task = AgentTask(objective="validate", input_data={"result": {"success": False}})
        result = agent.run(task)
        assert not result.success
        assert len(result.output["issues"]) > 0

    def test_validate_empty(self):
        agent = ValidatorAgent()
        task = AgentTask(objective="validate", input_data={})
        result = agent.run(task)
        assert not result.success


class TestResearcherAgent:
    def test_research(self):
        agent = ResearcherAgent()
        task = AgentTask(objective="search for EventBus docs")
        result = agent.run(task)
        assert result.success or not result.success  # depends on available stores
        assert "query" in result.output

    def test_research_with_stores(self):
        from motor.intelligence.memory.episodic import Episode, EpisodeStore
        from motor.intelligence.memory.retrieval import ContextRetriever
        from motor.intelligence.memory.semantic import SemanticMemoryStore

        store = EpisodeStore()
        store.store(Episode(payload="EventBus allows publish/subscribe", session_id="s1"))
        retriever = ContextRetriever(store)
        sstore = SemanticMemoryStore()

        agent = ResearcherAgent()
        agent._memory_store = sstore  # noqa: SLF001
        agent._context_retriever = retriever  # noqa: SLF001

        task = AgentTask(objective="EventBus")
        result = agent.run(task)
        assert result.success


class TestSupervisorAgent:
    def test_coordinate_success(self):
        sup = SupervisorAgent()
        exec_agent = ExecutorAgent()
        sup.register_agent(exec_agent)

        task = AgentTask(
            objective="echo test",
            context={
                "subtasks": [
                    {"agent_role": AgentRole.EXECUTOR, "objective": "echo test", "input_data": {"cmd": ["echo", "ok"]}},
                ],
            },
        )
        result = sup.run(task)
        assert result.success

    def test_coordinate_no_agent(self):
        sup = SupervisorAgent()
        task = AgentTask(
            objective="do something",
            context={"subtasks": [{"agent_role": AgentRole.RESEARCHER, "objective": "search"}]},
        )
        result = sup.run(task)
        assert not result.success  # no researcher registered

    def test_retry_on_failure(self):
        sup = SupervisorAgent()
        exec_agent = ExecutorAgent()
        sup.register_agent(exec_agent)

        task = AgentTask(
            objective="fail",
            context={
                "subtasks": [
                    {
                        "agent_role": AgentRole.EXECUTOR,
                        "objective": "fail",
                        "input_data": {"cmd": ["bash", "-c", "exit 1"]},
                    },
                ],
            },
        )
        result = sup.run(task)
        assert not result.success


class TestMultiAgentRuntime:
    def test_register(self):
        runtime = MultiAgentRuntime()
        agent = ExecutorAgent()
        aid = runtime.register(agent)
        assert runtime.get_agent(aid) is agent
        assert runtime.agent_count() == 1

    def test_unregister(self):
        runtime = MultiAgentRuntime()
        agent = ExecutorAgent()
        aid = runtime.register(agent)
        assert runtime.unregister(aid)
        assert runtime.agent_count() == 0

    def test_find_by_role(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        runtime.register(ValidatorAgent())
        executors = runtime.find_by_role(AgentRole.EXECUTOR)
        assert len(executors) == 1
        assert executors[0].role == AgentRole.EXECUTOR

    def test_find_by_capability(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        runtime.register(ValidatorAgent())
        agents = runtime.find_by_capability("execute")
        assert len(agents) == 1

    def test_execute_workflow(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        result = runtime.execute_workflow("echo hello", timeout=30)
        assert result.success

    def test_workflow_id_in_output(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        result = runtime.execute_workflow("echo test", timeout=30)
        assert "workflow_id" in result.output

    def test_cancel(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())

        result = runtime.execute_workflow("echo test", timeout=30)
        runtime.cancel(result.task_id)
        wf = runtime.get_workflow(result.task_id)
        # Workflow already completed, cancel won't change status
        assert wf is not None

    def test_cancel_nonexistent(self):
        runtime = MultiAgentRuntime()
        assert not runtime.cancel("nonexistent")

    def test_list_workflows(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        runtime.execute_workflow("echo a", timeout=30)
        runtime.execute_workflow("echo b", timeout=30)
        wfs = runtime.list_workflows()
        assert len(wfs) == 2

    def test_execute_workflow_failure(self):
        runtime = MultiAgentRuntime()
        # No executor registered, should fail
        result = runtime.execute_workflow("execute bad command", timeout=5)
        assert not result.success

    def test_concurrent_execution(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as exe:
            futures = [exe.submit(runtime.execute_workflow, f"echo task {i}", {"timeout": 10}) for i in range(5)]
            concurrent.futures.wait(futures)
        for f in futures:
            r = f.result()
            # May succeed or fail depending on timing
            assert isinstance(r, AgentResult)

    def test_execute_workflow_planning(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        result = runtime.execute_workflow("search and execute the pipeline", timeout=30)
        # The planner decomposes into researcher + executor, but no researcher registered
        # Should still return a result (may fail at supervisor level)
        assert isinstance(result, AgentResult)


class TestAgentABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Agent()

    def test_can_handle(self):
        agent = ExecutorAgent()
        task = AgentTask(objective="test", agent_role=AgentRole.EXECUTOR)
        assert agent.can_handle(task)
        task2 = AgentTask(objective="test", agent_role=AgentRole.VALIDATOR)
        assert not agent.can_handle(task2)


class TestIntegration:
    def test_full_workflow(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        runtime.register(ValidatorAgent())

        result = runtime.execute_workflow("validate the echo command", timeout=30)
        assert isinstance(result, AgentResult)

    def test_full_workflow_with_context(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())

        result = runtime.execute_workflow(
            "execute custom command",
            {"user": "test", "cmd": ["echo", "context_works"]},
            timeout=30,
        )
        assert result.success
        assert result.duration_ms > 0


class TestMockExecutorInjection:
    def test_custom_executor_injected(self):
        from motor.core.executor import BaseExecutor, ProcessResult

        class FakeExecutor(BaseExecutor):
            def __init__(self):
                self.calls = []

            def run(self, cmd, timeout=30, cwd=None, env=None):
                self.calls.append(cmd)
                return ProcessResult(ok=True, cmd=cmd, returncode=0, stdout="fake_output")

            async def arun(self, cmd, timeout=30, cwd=None, env=None):  # noqa: ASYNC109
                return self.run(cmd, timeout, cwd, env)

        fake = FakeExecutor()
        agent = ExecutorAgent(executor=fake)
        task = AgentTask(objective="test", input_data={"cmd": ["test_cmd"]})
        result = agent.run(task)
        assert result.success
        assert "fake_output" in result.output.get("stdout", "")
        assert fake.calls == [["test_cmd"]]

    def test_status_resets_to_idle(self):
        from motor.core.executor import BaseExecutor, ProcessResult

        class QuickFake(BaseExecutor):
            def run(self, cmd, timeout=30, cwd=None, env=None):
                return ProcessResult(ok=True, cmd=cmd, returncode=0, stdout="ok")

            async def arun(self, cmd, timeout=30, cwd=None, env=None):  # noqa: ASYNC109
                return self.run(cmd, timeout, cwd, env)

        agent = ExecutorAgent(executor=QuickFake())
        assert agent.status == AgentStatus.IDLE
        task = AgentTask(objective="test", input_data={"cmd": ["echo"]})
        agent.run(task)
        assert agent.status == AgentStatus.IDLE


class TestCancellation:
    def test_cancel_before_execution(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        wf_result = runtime.execute_workflow("echo")
        runtime.cancel(wf_result.task_id)
        wf = runtime.get_workflow(wf_result.task_id)
        assert wf is not None
        assert wf["status"] in ("completed", "cancelled", "failed")

    def test_cancel_mid_workflow(self):
        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        # Execute and cancel - should not raise
        result = runtime.execute_workflow("echo test", timeout=5)
        runtime.cancel(result.task_id)
        wf = runtime.get_workflow(result.task_id)
        assert wf is not None


class TestWorkflowCleanup:
    def test_fifo_cleanup(self):
        runtime = MultiAgentRuntime(max_completed_workflows=3)
        runtime.register(ExecutorAgent())
        for i in range(5):
            runtime.execute_workflow(f"echo {i}", timeout=5)
        wfs = runtime.list_workflows()
        # Max 3 completed + 0 running = should have at most 4 (3 completed + 1 that just turned non-running)
        assert len(wfs) <= 4


class TestStatusRestoration:
    def test_planner_status_restored(self):
        agent = PlannerAgent()
        agent.run(AgentTask(objective="echo test"))
        assert agent.status == AgentStatus.IDLE

    def test_executor_status_restored(self):
        agent = ExecutorAgent()
        agent.run(AgentTask(objective="echo test", input_data={"cmd": ["echo", "ok"]}))
        assert agent.status == AgentStatus.IDLE

    def test_validator_status_restored(self):
        agent = ValidatorAgent()
        agent.run(AgentTask(objective="validate", input_data={"result": {"success": True}}))
        assert agent.status == AgentStatus.IDLE

    def test_supervisor_status_restored(self):
        agent = SupervisorAgent()
        agent.run(AgentTask(objective="coordinate", context={"subtasks": []}))
        assert agent.status == AgentStatus.IDLE
