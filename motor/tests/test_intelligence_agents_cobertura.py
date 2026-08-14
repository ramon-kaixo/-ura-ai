"""Cobertura 100x100 de motor/intelligence/agents (TASK-20260814-001).

Cubre los remanentes no tocados por tests/unit/test_f27_b2_agents.py,
test_f27_b6_planner.py, test_motor_planner_readiness.py y
test_motor_public_api.py: base, message, executor, researcher, validator,
parallel, consensus, reflection, supervisor y runtime.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.consensus import (
    AgentWeightRegistry,
    MajorityVoting,
    UnanimousVoting,
    VotingEngine,
    VotingStrategy,
    WeightedConsensus,
    normalized_confidence,
)
from motor.intelligence.agents.executor import ExecutorAgent
from motor.intelligence.agents.message import AgentMessage, AgentResult, AgentRole, AgentStatus, AgentTask
from motor.intelligence.agents.parallel import ParallelExecutor
from motor.intelligence.agents.planner import PlannerAgent
from motor.intelligence.agents.reflection import (
    AlwaysRejectStrategy,
    ReflectionAction,
    ReflectionAgent,
    ReflectionDecision,
    ReflectionStrategy,
    RuleBasedReflectionStrategy,
)
from motor.intelligence.agents.researcher import ResearcherAgent
from motor.intelligence.agents.runtime import MultiAgentRuntime
from motor.intelligence.agents.supervisor import SupervisorAgent
from motor.intelligence.agents.validator import ValidatorAgent


def _task(objective: str = "execute tarea", role: AgentRole = AgentRole.EXECUTOR) -> AgentTask:
    return AgentTask(objective=objective, agent_role=role, context={"k": "v"}, input_data={"cmd": ["echo", "ok"]})


def _result(success: bool = True, output: dict[str, Any] | None = None, error: str = "") -> AgentResult:
    return AgentResult(task_id="t1", agent_id="a1", success=success, output=output or {}, error=error)


# ---------------------------------------------------------------- message.py


class TestMessageContracts:
    def test_agent_message_defaults(self) -> None:
        m = AgentMessage(source="s", target="t", message_type="task", payload={"a": 1})
        assert m.id
        assert m.timestamp
        assert m.correlation_id == m.id

    def test_agent_message_provided(self) -> None:
        m = AgentMessage(
            source="s",
            target="t",
            message_type="result",
            payload={},
            correlation_id="c1",
            id="m1",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        assert m.correlation_id == "c1"
        assert m.id == "m1"
        assert m.timestamp == "2026-01-01T00:00:00+00:00"

    def test_agent_task_defaults(self) -> None:
        t = AgentTask(objective="o")
        assert t.id
        assert t.created_at
        assert t.context == {}
        assert t.input_data == {}

    def test_agent_task_provided(self) -> None:
        t = AgentTask(objective="o", id="x1", created_at="2026-01-01T00:00:00+00:00")
        assert t.id == "x1"
        assert t.created_at == "2026-01-01T00:00:00+00:00"

    def test_agent_result_defaults(self) -> None:
        r = AgentResult(task_id="t", agent_id="a", success=True)
        assert r.id

    def test_agent_result_provided(self) -> None:
        r = AgentResult(task_id="t", agent_id="a", success=True, id="r1")
        assert r.id == "r1"


# ---------------------------------------------------------------- base.py


class TestAgentBase:
    def test_can_handle_match(self) -> None:
        agent = ValidatorAgent()
        assert agent.can_handle(_task(role=AgentRole.VALIDATOR))

    def test_can_handle_mismatch(self) -> None:
        agent = ValidatorAgent()
        assert not agent.can_handle(_task(role=AgentRole.EXECUTOR))


# ---------------------------------------------------------------- executor.py


class _OkExecutor:
    def run(self, cmd: list[str], timeout: int = 30, cwd: str | None = None, env: dict | None = None) -> Any:
        return SimpleNamespace(stdout="ok out", stderr="", returncode=0)


class _FailExecutor:
    def run(self, cmd: list[str], timeout: int = 30, cwd: str | None = None, env: dict | None = None) -> Any:
        return SimpleNamespace(stdout="", stderr="boom", returncode=1)


class _RaisingExecutor:
    def run(self, cmd: list[str], timeout: int = 30, cwd: str | None = None, env: dict | None = None) -> Any:
        raise RuntimeError("executor exploded")


class TestExecutorAgent:
    def test_default_executor_constructs_and_runs(self) -> None:
        agent = ExecutorAgent()
        assert agent.role == AgentRole.EXECUTOR
        res = agent.run(_task())
        assert res.success
        assert "ok" in res.output["stdout"]
        assert agent.status == AgentStatus.IDLE

    def test_success_with_cmd(self) -> None:
        agent = ExecutorAgent(executor=_OkExecutor())
        res = agent.run(_task())
        assert res.success
        assert res.output["objective"] == "execute tarea"
        assert res.output["stdout"] == "ok out"
        assert res.duration_ms >= 0

    def test_allow_failure(self) -> None:
        agent = ExecutorAgent(executor=_FailExecutor())
        task = _task()
        task.input_data["allow_failure"] = True
        res = agent.run(task)
        assert res.success
        assert res.output["returncode"] == 1

    def test_failure_raises_runtime_error(self) -> None:
        agent = ExecutorAgent(executor=_FailExecutor())
        res = agent.run(_task())
        assert not res.success
        assert "Command failed" in res.error

    def test_executor_exception(self) -> None:
        agent = ExecutorAgent(executor=_RaisingExecutor())
        res = agent.run(_task())
        assert not res.success
        assert "executor exploded" in res.error

    def test_custom_agent_id(self) -> None:
        agent = ExecutorAgent(agent_id="ex1", executor=_OkExecutor())
        assert agent.id == "ex1"
        assert agent.capabilities == ["execute", "run", "compute"]


# ---------------------------------------------------------------- researcher.py


class _Fact:
    def to_dict(self) -> dict[str, Any]:
        return {"text": "facto"}


class _Episodes:
    def to_dict(self) -> dict[str, Any]:
        return {"episodes": [1, 2]}


class _MemoryStore:
    def __init__(self, facts: list[_Fact] | None = None, error: bool = False) -> None:
        self._facts = facts or []
        self._error = error

    def search(self, text: str, k: int = 5) -> list[_Fact]:
        if self._error:
            raise RuntimeError("memory down")
        return self._facts


class _Retriever:
    def __init__(self, episodes: _Episodes | None = None) -> None:
        self._episodes = episodes

    def search(self, query: Any) -> _Episodes | None:
        return self._episodes


class TestResearcherAgent:
    def test_init_provided(self) -> None:
        agent = ResearcherAgent(agent_id="r1", memory_store=_MemoryStore(), context_retriever=_Retriever())
        assert agent.id == "r1"
        assert agent.role == AgentRole.RESEARCHER

    def test_auto_discover_success(self) -> None:
        agent = ResearcherAgent()
        assert agent._memory_store is not None
        assert agent._context_retriever is not None

    def test_auto_discover_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("no store")

        monkeypatch.setattr("motor.intelligence.memory.episodic.EpisodeStore", boom)
        monkeypatch.setattr("motor.intelligence.memory.semantic.SemanticMemoryStore", boom)
        agent = ResearcherAgent()
        assert agent._memory_store is None
        assert agent._context_retriever is None

    def test_semantic_sources(self) -> None:
        agent = ResearcherAgent(memory_store=_MemoryStore(facts=[_Fact()]), context_retriever=None)
        res = agent.run(_task(objective="buscar x", role=AgentRole.RESEARCHER))
        assert res.success
        assert res.output["sources"] == ["semantic_memory"]
        assert res.output["semantic_facts"] == [{"text": "facto"}]

    def test_episodic_sources(self) -> None:
        agent = ResearcherAgent(memory_store=None, context_retriever=_Retriever(episodes=_Episodes()))
        res = agent.run(_task(objective="buscar x", role=AgentRole.RESEARCHER))
        assert res.success
        assert res.output["sources"] == ["episodic_memory"]
        assert res.output["episodes"] == {"episodes": [1, 2]}

    def test_no_sources(self) -> None:
        agent = ResearcherAgent(memory_store=_MemoryStore(), context_retriever=_Retriever())
        res = agent.run(_task(objective="nada", role=AgentRole.RESEARCHER))
        assert res.success
        assert res.output["sources"] == []

    def test_search_exception(self) -> None:
        agent = ResearcherAgent(memory_store=_MemoryStore(error=True), context_retriever=None)
        res = agent.run(_task(objective="x", role=AgentRole.RESEARCHER))
        assert not res.success
        assert "memory down" in res.error


# ---------------------------------------------------------------- validator.py


class TestValidatorAgent:
    def test_no_result_data(self) -> None:
        res = ValidatorAgent().run(_task())
        assert not res.success
        assert "No result data" in res.output["issues"][0]

    def test_require_success_failure(self) -> None:
        task = _task()
        task.input_data = {"result": {"success": False}}
        res = ValidatorAgent().run(task)
        assert not res.success
        assert "failure" in res.output["issues"][0]

    def test_require_output_missing(self) -> None:
        task = _task()
        task.input_data = {"result": {"success": True}, "require_output": True}
        res = ValidatorAgent().run(task)
        assert not res.success
        assert "no output" in res.output["issues"][0]

    def test_valid(self) -> None:
        task = _task()
        task.input_data = {"result": {"success": True, "output": "x"}, "require_output": True}
        res = ValidatorAgent().run(task)
        assert res.success
        assert res.output["valid"] is True

    def test_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("validate crashed")

        monkeypatch.setattr(ValidatorAgent, "_validate", boom)
        res = ValidatorAgent().run(_task())
        assert not res.success
        assert "validate crashed" in res.error


# ---------------------------------------------------------------- consensus.py


class _StubStrategy(VotingStrategy):
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name

    def aggregate(self, results: list[AgentResult]) -> Any:
        return SimpleNamespace(outcome={"stub": True})


class TestConsensus:
    def test_majority_empty(self) -> None:
        res = MajorityVoting().aggregate([])
        assert not res.success
        assert res.total_votes == 0

    def test_majority_single_winner(self) -> None:
        results = [
            _result(output={"ans": "a"}),
            _result(output={"ans": "a"}),
            _result(output={"ans": "b"}),
        ]
        res = MajorityVoting().aggregate(results)
        assert res.success
        assert res.outcome == {"ans": "a"}
        assert res.vote_counts == {"[('ans', 'a')]": 2, "[('ans', 'b')]": 1}

    def test_majority_tie(self) -> None:
        results = [_result(output={"ans": "a"}), _result(output={"ans": "b"})]
        res = MajorityVoting().aggregate(results)
        assert not res.success
        assert res.outcome["_tie"] is True
        assert set(res.outcome["_tied_keys"]) == {"[('ans', 'a')]", "[('ans', 'b')]"}

    def test_majority_error_keys(self) -> None:
        results = [_result(success=False, output={}, error="e1"), _result(success=False, output={}, error="e2")]
        res = MajorityVoting().aggregate(results)
        assert not res.success
        assert set(res.vote_counts) == {"error:e1", "error:e2"}

    def test_unanimous_empty(self) -> None:
        res = UnanimousVoting().aggregate([])
        assert not res.success

    def test_unanimous_single(self) -> None:
        res = UnanimousVoting().aggregate([_result(output={"v": 1})])
        assert res.success
        assert res.outcome == {"v": 1}

    def test_unanimous_all_agree(self) -> None:
        results = [_result(output={"v": 1}), _result(output={"v": 1}), _result(output={"v": 1})]
        res = UnanimousVoting().aggregate(results)
        assert res.success
        assert res.vote_counts == {"[('v', 1)]": 3}

    def test_unanimous_disagree(self) -> None:
        results = [_result(output={"v": 1}), _result(output={"v": 2})]
        res = UnanimousVoting().aggregate(results)
        assert not res.success
        assert res.outcome["_unanimous_failed"] is True

    def test_vote_summary(self) -> None:
        res = MajorityVoting().aggregate([_result(output={"v": 1})])
        assert res.vote_summary.startswith("majority: ")
        assert res.vote_summary.endswith("(1 votes)")

    def test_normalized_confidence_variants(self) -> None:
        assert normalized_confidence(_result(output={})) == 1.0
        assert normalized_confidence(_result(output={"confidence": "alto"})) == 1.0
        assert normalized_confidence(_result(output={"confidence": 2.5})) == 1.0
        assert normalized_confidence(_result(output={"confidence": -1.0})) == 0.0
        assert normalized_confidence(_result(output={"confidence": 0.5})) == 0.5

    def test_weight_registry(self) -> None:
        reg = AgentWeightRegistry()
        reg.set_weight("a", 2.0)
        reg.set_weight("b", -3.0)
        assert reg.get_weight("a") == 2.0
        assert reg.get_weight("b") == 0.0
        assert reg.get_weight("unknown") == 1.0
        assert reg.all_weights() == {"a": 2.0, "b": 0.0}
        assert reg.reset_agent("a") is True
        assert reg.reset_agent("a") is False
        reg.reset()
        assert reg.all_weights() == {}

    def test_voting_engine_default_and_setter(self) -> None:
        engine = VotingEngine()
        assert isinstance(engine.strategy, MajorityVoting)
        unanimous = UnanimousVoting()
        engine.strategy = unanimous
        assert engine.strategy is unanimous
        assert engine.vote([_result()]).success

    def test_voting_engine_register(self) -> None:
        engine = VotingEngine()
        engine.register_strategy(_StubStrategy("stub"))
        assert engine.get_strategy("stub") is not None
        assert engine.get_strategy("nope") is None
        assert engine.vote_with([_result()], "stub").outcome == {"stub": True}

    def test_voting_engine_unknown_strategy(self) -> None:
        engine = VotingEngine()
        with pytest.raises(ValueError, match="Unknown strategy"):
            engine.vote_with([_result()], "nope")

    def test_weighted_empty(self) -> None:
        res = WeightedConsensus().aggregate([])
        assert not res.success
        assert res.weighted is True

    def test_weighted_winner(self) -> None:
        results = [_result(output={"w": 1}), _result(output={"w": 1})]
        res = WeightedConsensus().aggregate(results)
        assert res.success
        assert res.outcome == {"w": 1}
        assert res.weight_details

    def test_weighted_tie(self) -> None:
        results = [_result(output={"w": 1}), _result(output={"w": 2})]
        res = WeightedConsensus().aggregate(results)
        assert not res.success
        assert res.outcome["_tie"] is True

    def test_weighted_registry(self) -> None:
        reg = AgentWeightRegistry()
        reg.set_weight("a1", 0.5)
        consensus = WeightedConsensus(reg)
        assert consensus.registry is reg


# ---------------------------------------------------------------- parallel.py


class _StubAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        capabilities: list[str] | None = None,
        outcome: AgentResult | None = None,
        error: Exception | None = None,
        started: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.id = agent_id
        self.name = role.value
        self.role = role
        self.capabilities = capabilities or [role.value]
        self.status = AgentStatus.IDLE
        self._outcome = outcome
        self._error = error
        self._started = started
        self._release = release

    def run(self, task: AgentTask) -> AgentResult:
        if self._started:
            self._started.set()
        if self._release:
            self._release.wait(10)
        if self._error:
            raise self._error
        return self._outcome or _result(success=True, output={"task": task.objective})


class _BlockingAgent(Agent):
    def __init__(self, started: threading.Event, release: threading.Event) -> None:
        self.id = "block"
        self.name = "block"
        self.role = AgentRole.EXECUTOR
        self.capabilities = ["block"]
        self.status = AgentStatus.IDLE
        self._started = started
        self._release = release

    def run(self, task: AgentTask) -> AgentResult:
        self._started.set()
        self._release.wait(10)
        return _result()


class _SlowAgent(Agent):
    def __init__(self, delay: float = 0.3) -> None:
        self.id = "slow"
        self.name = "slow"
        self.role = AgentRole.EXECUTOR
        self.capabilities = ["slow"]
        self.status = AgentStatus.IDLE
        self._delay = delay

    def run(self, task: AgentTask) -> AgentResult:
        time.sleep(self._delay)
        return _result()


class TestParallelExecutor:
    def test_init_and_max_workers(self) -> None:
        assert ParallelExecutor().max_workers == 4
        assert ParallelExecutor(max_workers=0).max_workers == 1
        assert ParallelExecutor(max_workers=8).max_workers == 8

    def test_cancel_flow(self) -> None:
        p = ParallelExecutor()
        assert p.cancel("wf1") is True
        assert p.cancel("wf1") is False
        assert p.is_cancelled("wf1") is True

    def test_execute_empty(self) -> None:
        p = ParallelExecutor()
        res = p.execute([])
        assert res.total_tasks == 0
        assert res.success

    def test_execute_cancelled_before(self) -> None:
        p = ParallelExecutor()
        p.cancel("wf-x")
        res = p.execute([("a1", _task())], workflow_id="wf-x")
        assert res.cancelled == 1
        assert res.cancelled_by_user is True

    def test_agent_not_found(self) -> None:
        p = ParallelExecutor()
        res = p.execute([("ghost", _task())], workflow_id="wf-ghost")
        assert res.failed == 1
        assert "agent_not_found:ghost" in res.errors[0]

    def test_success(self) -> None:
        agent = _StubAgent("a1", AgentRole.EXECUTOR)
        p = ParallelExecutor(find_agent_fn=lambda aid: agent if aid == "a1" else None)
        res = p.execute([("a1", _task())], workflow_id="wf-ok")
        assert res.completed == 1
        assert res.success

    def test_failure(self) -> None:
        agent = _StubAgent("a1", AgentRole.EXECUTOR, outcome=_result(success=False, error="nope"))
        p = ParallelExecutor(find_agent_fn=lambda aid: agent)
        res = p.execute([("a1", _task())], workflow_id="wf-fail")
        assert res.failed == 1
        assert "nope" in res.errors[0]

    def test_fail_fast(self) -> None:
        failing = _StubAgent("f", AgentRole.EXECUTOR, outcome=_result(success=False, error="fast-fail"))
        slow = _SlowAgent(delay=0.05)
        p = ParallelExecutor(find_agent_fn=lambda aid: failing if aid == "f" else slow, fail_fast=True)
        res = p.execute([("f", _task()), ("slow", _task())], workflow_id="wf-ff")
        assert res.failed == 1
        assert res.cancelled == 1

    def test_cancel_on_error(self) -> None:
        failing = _StubAgent("f", AgentRole.EXECUTOR, outcome=_result(success=False, error="err"))
        slow = _SlowAgent(delay=0.05)
        p = ParallelExecutor(find_agent_fn=lambda aid: failing if aid == "f" else slow, cancel_on_error=True)
        res = p.execute([("f", _task()), ("slow", _task())], workflow_id="wf-coe")
        assert res.failed == 1
        assert res.cancelled == 1

    def test_global_timeout(self) -> None:
        p = ParallelExecutor(find_agent_fn=lambda aid: _SlowAgent(delay=0.4), global_timeout=0.1)
        res = p.execute([("slow", _task())], workflow_id="wf-tmo")
        assert res.timed_out == 1
        assert "timed_out" in res.errors[0]

    def test_deadline_branch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        index = {"i": 0}

        def fake_monotonic() -> float:
            index["i"] += 1
            return 999.0 if index["i"] > 4 else 0.0

        monkeypatch.setattr("motor.intelligence.agents.parallel.time.monotonic", fake_monotonic)
        p = ParallelExecutor(find_agent_fn=lambda aid: _SlowAgent(delay=0.001), global_timeout=5.0)
        res = p.execute([("slow", _task())], workflow_id="wf-deadline")
        assert res.timed_out == 1
        assert "global timeout" in res.errors[0]

    def test_inner_except_branch(self) -> None:
        def boom_finder(aid: str) -> Any:
            raise RuntimeError("finder crash")

        p = ParallelExecutor(find_agent_fn=boom_finder)
        res = p.execute([("slow", _task())], workflow_id="wf-exc")
        assert res.timed_out == 1
        assert "finder crash" in res.errors[0]

    def test_cancel_mid_execution(self) -> None:
        started = threading.Event()
        release = threading.Event()
        p = ParallelExecutor(find_agent_fn=lambda aid: _BlockingAgent(started, release))
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            fut = executor.submit(p.execute, [("block", _task())], "wf-mid")
            assert started.wait(5)
            assert p.cancel("wf-mid") is True
            release.set()
            res = fut.result(timeout=10)
            assert res.cancelled == 1
        finally:
            release.set()
            executor.shutdown()

    def test_cancel_stops_submission_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agents = {"block": _StubAgent("block", AgentRole.EXECUTOR), "block2": _StubAgent("block2", AgentRole.EXECUTOR)}
        p = ParallelExecutor(find_agent_fn=lambda aid: agents[aid])
        checks = iter([False, True])
        monkeypatch.setattr(p, "is_cancelled", lambda wf: next(checks))
        res = p.execute([("block", _task()), ("block2", _task())], workflow_id="wf-loop")
        assert res.cancelled == 2
        assert res.cancelled_by_user is True

    def test_run_single_cancelled(self) -> None:
        p = ParallelExecutor()
        p.cancel("wf-d")
        res = p._run_single("a1", _task(), "wf-d")
        assert not res.success
        assert res.error == "cancelled"

    def test_run_single_agent_none(self) -> None:
        p = ParallelExecutor()
        res = p._run_single("nobody", _task(), "wf-d2")
        assert not res.success
        assert res.error == "agent_not_found:nobody"

    def test_run_single_exception(self) -> None:
        agent = _StubAgent("a1", AgentRole.EXECUTOR, error=RuntimeError("kaboom"))
        p = ParallelExecutor(find_agent_fn=lambda aid: agent)
        res = p._run_single("a1", _task(), "wf-d3")
        assert not res.success
        assert "kaboom" in res.error

    def test_close(self) -> None:
        p = ParallelExecutor()
        p.cancel("wf-c")
        p.close()
        assert not p.is_cancelled("wf-c")


# ---------------------------------------------------------------- reflection.py


class _SequenceStrategy(ReflectionStrategy):
    def __init__(self, decisions: list[ReflectionDecision]) -> None:
        self._decisions = decisions

    def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
        return self._decisions[min(iteration, len(self._decisions) - 1)]


class _RaisingStrategy(ReflectionStrategy):
    def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
        raise RuntimeError("strategy boom")


class TestReflection:
    def test_rule_based_failure(self) -> None:
        decision = RuleBasedReflectionStrategy().reflect(_result(success=False, error="x"), 0)
        assert decision.action == ReflectionAction.REVISE
        assert decision.metadata["result_error"] == "x"

    def test_rule_based_accept(self) -> None:
        decision = RuleBasedReflectionStrategy(min_confidence=0.7).reflect(_result(output={"confidence": 0.9}), 0)
        assert decision.action == ReflectionAction.ACCEPT
        assert "above_threshold" in decision.reason

    def test_rule_based_below_threshold(self) -> None:
        decision = RuleBasedReflectionStrategy(min_confidence=0.7).reflect(_result(output={"confidence": 0.5}), 0)
        assert decision.action == ReflectionAction.REVISE
        assert "below_threshold" in decision.reason

    def test_rule_based_non_numeric_confidence(self) -> None:
        decision = RuleBasedReflectionStrategy(min_confidence=0.7).reflect(_result(output={"confidence": "alta"}), 0)
        assert decision.action == ReflectionAction.ACCEPT
        decision = RuleBasedReflectionStrategy(min_confidence=0.7).reflect(_result(output={"confidence": 2.0}), 0)
        assert decision.action == ReflectionAction.ACCEPT
        decision = RuleBasedReflectionStrategy(min_confidence=0.7).reflect(_result(output={"confidence": -1.0}), 0)
        assert decision.action == ReflectionAction.REVISE

    def test_always_reject(self) -> None:
        decision = AlwaysRejectStrategy().reflect(_result(), 3)
        assert decision.action == ReflectionAction.REJECT
        assert decision.iteration == 3

    def test_agent_init_and_properties(self) -> None:
        agent = ReflectionAgent()
        assert isinstance(agent.strategy, RuleBasedReflectionStrategy)
        strategy = AlwaysRejectStrategy()
        agent.strategy = strategy
        assert agent.strategy is strategy
        clamped = ReflectionAgent(max_iterations=0, min_confidence=-1.0)
        assert clamped._max_iterations == 1
        assert clamped._min_confidence == 0.0
        high = ReflectionAgent(min_confidence=2.0)
        assert high._min_confidence == 1.0

    def test_reflect_on(self) -> None:
        agent = ReflectionAgent()
        decision = agent.reflect_on(_result(output={"confidence": 0.95}))
        assert decision.action == ReflectionAction.ACCEPT

    def test_run_accept(self) -> None:
        agent = ReflectionAgent()
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": _result(output={"confidence": 0.99})}
        res = agent.run(task)
        assert res.success
        assert res.output["stopped_by"] == "accept"
        assert agent.status == AgentStatus.IDLE

    def test_run_no_initial(self) -> None:
        res = ReflectionAgent().run(_task(role=AgentRole.VALIDATOR))
        assert not res.success
        assert res.error == "no_initial_result_provided"

    def test_run_initial_not_agent_result(self) -> None:
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": {"not": "a result"}}
        res = ReflectionAgent().run(task)
        assert not res.success
        assert res.error == "initial_result_not_agent_result"

    def test_run_stop(self) -> None:
        agent = ReflectionAgent(strategy=_SequenceStrategy([ReflectionDecision(action=ReflectionAction.STOP)]))
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": _result()}
        res = agent.run(task)
        assert res.success
        assert res.output["stopped_by"] == "stop"

    def test_run_accept_confidence_no_stop(self) -> None:
        agent = ReflectionAgent(
            strategy=_SequenceStrategy([ReflectionDecision(action=ReflectionAction.ACCEPT, confidence=0.95)]),
            stop_on_accept=False,
        )
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": _result(output={"confidence": 0.95})}
        res = agent.run(task)
        assert res.output["stopped_by"] == "confidence"

    def test_run_accept_below_threshold_max_iterations(self) -> None:
        agent = ReflectionAgent(
            strategy=_SequenceStrategy([ReflectionDecision(action=ReflectionAction.ACCEPT, confidence=0.5)]),
            stop_on_accept=False,
            min_confidence=0.9,
            max_iterations=1,
        )
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": _result(output={"confidence": 0.5})}
        res = agent.run(task)
        assert res.output["stopped_by"] == "max_iterations"
        assert res.output["iterations"] == 1

    def test_run_reject(self) -> None:
        agent = ReflectionAgent(strategy=AlwaysRejectStrategy())
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": _result()}
        res = agent.run(task)
        assert not res.success
        assert res.output["stopped_by"] == "reject"

    def test_run_revise_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        agent = ReflectionAgent(
            strategy=_SequenceStrategy([ReflectionDecision(action=ReflectionAction.REVISE)]),
            max_iterations=1,
        )
        monkeypatch.setattr(agent, "_revise", lambda r, d: None)
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": _result()}
        res = agent.run(task)
        assert res.output["stopped_by"] == "revise_failed"
        assert res.output["reason"] == "revise_failed_no_new_result"

    def test_run_revise_then_accept(self) -> None:
        agent = ReflectionAgent(
            strategy=_SequenceStrategy(
                [
                    ReflectionDecision(action=ReflectionAction.REVISE, reason="fix it", iteration=0),
                    ReflectionDecision(action=ReflectionAction.ACCEPT, confidence=0.99, iteration=1),
                ],
            ),
        )
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": _result(output={"a": 1})}
        res = agent.run(task)
        assert res.success
        assert res.output["final"]["_revised"] is True
        assert res.output["reflections"][0]["action"] == "revise"

    def test_run_exception(self) -> None:
        agent = ReflectionAgent(strategy=_RaisingStrategy())
        task = _task(role=AgentRole.VALIDATOR)
        task.input_data = {"initial_result": _result()}
        res = agent.run(task)
        assert not res.success
        assert "strategy boom" in res.error

    def test_revise_without_output(self) -> None:
        agent = ReflectionAgent()
        revised = agent._revise(_result(success=True), ReflectionDecision(action=ReflectionAction.REVISE))
        assert revised is not None
        assert revised.output["_revised"] is True


# ---------------------------------------------------------------- supervisor.py


class TestSupervisorAgent:
    def test_register_and_find(self) -> None:
        sup = SupervisorAgent()
        agent = _StubAgent("a1", AgentRole.EXECUTOR)
        sup.register_agent(agent)
        assert sup._find_agent(AgentRole.EXECUTOR) is agent
        assert sup._find_agent(AgentRole.RESEARCHER) is None
        assert sup._find_agent(None) is None

    def test_run_empty_subtasks(self) -> None:
        res = SupervisorAgent().run(_task(role=AgentRole.SUPERVISOR))
        assert res.success
        assert res.output["total_steps"] == 0

    def test_cancelled_before(self) -> None:
        task = _task(role=AgentRole.SUPERVISOR)
        task.context = {"subtasks": [{"objective": "x"}], "_cancellation_check": lambda: True}
        res = SupervisorAgent().run(task)
        assert not res.success
        assert res.output["steps"][0]["status"] == "cancelled"

    def test_no_agent_skipped(self) -> None:
        task = _task(role=AgentRole.SUPERVISOR)
        task.context = {"subtasks": [{"objective": "x", "agent_role": AgentRole.EXECUTOR}]}
        res = SupervisorAgent().run(task)
        assert not res.success
        assert res.output["steps"][0]["status"] == "skipped"

    def test_role_none_skipped(self) -> None:
        task = _task(role=AgentRole.SUPERVISOR)
        task.context = {"subtasks": [{"objective": "x", "agent_role": None}]}
        res = SupervisorAgent().run(task)
        assert res.output["steps"][0]["status"] == "skipped"

    def test_subtask_success(self) -> None:
        sup = SupervisorAgent()
        sup.register_agent(_StubAgent("a1", AgentRole.EXECUTOR))
        task = _task(role=AgentRole.SUPERVISOR)
        task.context = {"subtasks": [{"objective": "hazlo", "agent_role": AgentRole.EXECUTOR}]}
        res = sup.run(task)
        assert res.success
        assert res.output["steps"][0]["status"] == "completed"
        assert res.output["steps"][0]["attempt"] == 1

    def test_subtask_failure_retries(self) -> None:
        sup = SupervisorAgent()
        sup.register_agent(_StubAgent("a1", AgentRole.EXECUTOR, outcome=_result(success=False, error="no")))
        task = _task(role=AgentRole.SUPERVISOR)
        task.context = {"subtasks": [{"objective": "hazlo", "agent_role": AgentRole.EXECUTOR}]}
        res = sup.run(task)
        assert not res.success
        failed_steps = [s for s in res.output["steps"] if s["status"] == "failed"]
        assert len(failed_steps) == 3

    def test_subtask_exception_retries(self) -> None:
        sup = SupervisorAgent()
        sup.register_agent(_StubAgent("a1", AgentRole.EXECUTOR, error=RuntimeError("oops")))
        task = _task(role=AgentRole.SUPERVISOR)
        task.context = {"subtasks": [{"objective": "hazlo", "agent_role": AgentRole.EXECUTOR}]}
        res = sup.run(task)
        assert not res.success
        error_steps = [s for s in res.output["steps"] if s["status"] == "error"]
        assert len(error_steps) == 3

    def test_cancelled_during_retry(self) -> None:
        state = {"runs": 0}

        def cancellable() -> bool:
            return state["runs"] >= 1

        def fail_first_then_success(task: AgentTask) -> AgentResult:
            state["runs"] += 1
            if state["runs"] == 1:
                return _result(success=False, error="intento1")
            return _result(success=True)

        sup = SupervisorAgent()
        sup.register_agent(_StubAgent("a1", AgentRole.EXECUTOR, outcome=_result(success=False, error="x")))
        sup._agents["a1"].run = fail_first_then_success
        task = _task(role=AgentRole.SUPERVISOR)
        task.context = {
            "subtasks": [{"objective": "hazlo", "agent_role": AgentRole.EXECUTOR}],
            "_cancellation_check": cancellable,
        }
        res = sup.run(task)
        assert res.output["steps"][-1]["status"] == "cancelled"

    def test_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("coord crash")

        monkeypatch.setattr(SupervisorAgent, "_coordinate", boom)
        res = SupervisorAgent().run(_task(role=AgentRole.SUPERVISOR))
        assert not res.success
        assert "coord crash" in res.error


# ---------------------------------------------------------------- runtime.py


class TestMultiAgentRuntime:
    def test_init_and_count(self) -> None:
        rt = MultiAgentRuntime()
        assert rt.agent_count() == 0

    def test_register_unregister(self) -> None:
        rt = MultiAgentRuntime()
        agent = _StubAgent("a1", AgentRole.EXECUTOR)
        assert rt.register(agent) == "a1"
        assert rt.get_agent("a1") is agent
        assert rt.unregister("a1") is True
        assert rt.unregister("a1") is False
        assert rt.get_agent("a1") is None

    def test_find_by_role_and_capability(self) -> None:
        rt = MultiAgentRuntime()
        agent = _StubAgent("a1", AgentRole.EXECUTOR, capabilities=["run", "plan"])
        rt.register(agent)
        assert rt.find_by_role(AgentRole.EXECUTOR) == [agent]
        assert rt.find_by_role(AgentRole.RESEARCHER) == []
        assert rt.find_by_capability("plan") == [agent]
        assert rt.find_by_capability("nonexistent") == []

    def test_execute_success_with_agent(self) -> None:
        rt = MultiAgentRuntime()
        rt.register(_StubAgent("a1", AgentRole.EXECUTOR))
        res = rt.execute_workflow("execute tarea")
        assert res.success
        assert res.output["workflow_id"]
        assert "plan" in res.output
        assert res.output["supervisor"]["steps"][0]["status"] == "completed"
        assert rt.get_workflow(res.output["workflow_id"])["status"] == "completed"

    def test_execute_no_agents(self) -> None:
        rt = MultiAgentRuntime()
        res = rt.execute_workflow("execute tarea")
        assert not res.success

    def test_execute_failing_agent(self) -> None:
        rt = MultiAgentRuntime()
        rt.register(_StubAgent("a1", AgentRole.EXECUTOR, outcome=_result(success=False, error="no")))
        res = rt.execute_workflow("execute tarea")
        assert not res.success
        assert res.error == ""

    def test_execute_cancelled_initial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(MultiAgentRuntime, "_is_cancelled", lambda self, wid: True)
        rt = MultiAgentRuntime()
        res = rt.execute_workflow("execute tarea")
        assert not res.success
        assert res.error == "cancelled"

    def test_execute_cancelled_after_plan(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = iter([False, True, False])
        monkeypatch.setattr(MultiAgentRuntime, "_is_cancelled", lambda self, wid: next(calls))
        rt = MultiAgentRuntime()
        res = rt.execute_workflow("execute tarea")
        assert not res.success
        assert res.error == "cancelled"

    def test_execute_plan_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rt = MultiAgentRuntime()
        monkeypatch.setattr(rt._planner, "run", lambda task: _result(success=False, error="plan bad"))
        res = rt.execute_workflow("execute tarea")
        assert not res.success
        assert res.error == "plan bad"

    def test_execute_planner_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rt = MultiAgentRuntime()

        def boom(task: AgentTask) -> AgentResult:
            raise RuntimeError("planner exploded")

        monkeypatch.setattr(rt._planner, "run", boom)
        res = rt.execute_workflow("execute tarea")
        assert not res.success
        assert "planner exploded" in res.error

    def test_cancel_running(self) -> None:
        started = threading.Event()
        release = threading.Event()
        rt = MultiAgentRuntime()
        rt.register(_StubAgent("a1", AgentRole.EXECUTOR, started=started, release=release))
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            fut = executor.submit(rt.execute_workflow, "execute tarea")
            assert started.wait(5)
            wf_id = rt.list_workflows()[0]["id"]
            assert rt.cancel(wf_id) is True
            release.set()
            res = fut.result(timeout=10)
            assert not res.success
            assert res.error == "cancelled"
            assert rt.get_workflow(wf_id)["status"] == "cancelled"
            assert rt.cancel(wf_id) is False
        finally:
            release.set()
            executor.shutdown()

    def test_cancel_all(self) -> None:
        started = threading.Event()
        release = threading.Event()
        rt = MultiAgentRuntime()
        rt.register(_StubAgent("a1", AgentRole.EXECUTOR, started=started, release=release))
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            fut = executor.submit(rt.execute_workflow, "execute tarea")
            assert started.wait(5)
            assert rt.cancel() == 1
            release.set()
            fut.result(timeout=10)
        finally:
            release.set()
            executor.shutdown()

    def test_list_workflows(self) -> None:
        rt = MultiAgentRuntime()
        rt.execute_workflow("execute tarea")
        assert len(rt.list_workflows()) == 1
        assert rt.list_workflows()[0]["status"] == "failed"

    def test_complete_unknown_workflow(self) -> None:
        rt = MultiAgentRuntime()
        res = rt._complete("nope", True, "", 0.0)
        assert res.success
        assert rt.get_workflow("nope") is None

    def test_trim_workflows(self) -> None:
        rt = MultiAgentRuntime(max_completed_workflows=2)
        rt.execute_workflow("execute uno")
        rt.execute_workflow("execute dos")
        first_id = rt.list_workflows()[0]["id"]
        rt.execute_workflow("execute tres")
        assert rt.get_workflow(first_id) is None
        assert len(rt.list_workflows()) == 2


# ---------------------------------------------------------------- planner.py


class TestPlannerAgent:
    def test_run_ok(self) -> None:
        planner = PlannerAgent(agent_id="p1")
        task = _task(objective="execute tarea", role=AgentRole.EXECUTOR)
        res = planner.run(task)
        assert res.success
        assert res.output["subtasks"]
        assert res.output["original_objective"] == "execute tarea"
        assert planner.status == AgentStatus.IDLE

    def test_run_exception(self) -> None:
        planner = PlannerAgent()

        class _TaskCon:  # objectivo no string -> .lower() falla
            pass

        task = AgentTask(objective=_TaskCon(), agent_role=AgentRole.EXECUTOR)
        res = planner.run(task)
        assert not res.success
        assert res.error

    def test_decompose_default_executor(self) -> None:
        planner = PlannerAgent()
        subtasks = planner._decompose("hola sin keywords", {})
        assert len(subtasks) == 1
        assert subtasks[0]["agent_role"] == AgentRole.EXECUTOR

    def test_decompose_inserts_researcher(self) -> None:
        planner = PlannerAgent()
        subtasks = planner._decompose("search this and execute that", {})
        roles = [s["agent_role"] for s in subtasks]
        assert roles[0] == AgentRole.RESEARCHER
        assert AgentRole.EXECUTOR in roles

    def test_decompose_keywords_multiples(self) -> None:
        planner = PlannerAgent()
        subtasks = planner._decompose("compute x validate y check z", {})
        roles = [s["agent_role"] for s in subtasks]
        assert AgentRole.VALIDATOR in roles
        assert AgentRole.EXECUTOR in roles


# ---------------------------------------------------------------- researcher.py (ramas)


class TestResearcherRamas:
    def test_run_sin_memory_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ResearcherAgent, "_auto_discover", lambda self: None)
        agent = ResearcherAgent(memory_store=None, context_retriever=_Retriever(episodes=_Episodes()))
        res = agent.run(_task(objective="x", role=AgentRole.RESEARCHER))
        assert res.success
        assert res.output["sources"] == ["episodic_memory"]

    def test_run_sin_context_retriever(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ResearcherAgent, "_auto_discover", lambda self: None)
        agent = ResearcherAgent(memory_store=_MemoryStore(facts=[_Fact()]), context_retriever=None)
        res = agent.run(_task(objective="x", role=AgentRole.RESEARCHER))
        assert res.success
        assert res.output["sources"] == ["semantic_memory"]


# ---------------------------------------------------------------- consensus.py (ramas)


class TestConsensusRamas:
    def test_outcome_para_no_primera_posicion(self) -> None:
        results = [
            _result(output={"w": 2}, error=""),
            _result(output={"w": 1}, error=""),
            _result(output={"w": 1}, error=""),
        ]
        res = WeightedConsensus().aggregate(results)
        assert res.success
        assert res.outcome == {"w": 1}
