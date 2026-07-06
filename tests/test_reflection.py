from __future__ import annotations

import pytest

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentStatus, AgentTask
from motor.intelligence.agents.reflection import (
    AlwaysRejectStrategy,
    ReflectionAction,
    ReflectionAgent,
    ReflectionDecision,
    ReflectionStrategy,
    RuleBasedReflectionStrategy,
)


def _result(success: bool, output: dict | None = None, agent_id: str = "") -> AgentResult:
    return AgentResult(task_id="t1", agent_id=agent_id or "test", success=success, output=output or {})


class TestReflectionDecision:
    def test_defaults(self):
        d = ReflectionDecision()
        assert d.action == ReflectionAction.ACCEPT
        assert d.confidence == 1.0
        assert d.iteration == 0


class TestReflectionStrategyABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ReflectionStrategy()


class TestRuleBasedReflectionStrategy:
    def test_accept_high_confidence(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.7)
        result = _result(True, {"confidence": 0.9})
        d = strategy.reflect(result, iteration=0)
        assert d.action == ReflectionAction.ACCEPT

    def test_revise_low_confidence(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.7)
        result = _result(True, {"confidence": 0.3})
        d = strategy.reflect(result, iteration=0)
        assert d.action == ReflectionAction.REVISE

    def test_revise_on_failure(self):
        strategy = RuleBasedReflectionStrategy()
        result = _result(False)
        d = strategy.reflect(result, iteration=0)
        assert d.action == ReflectionAction.REVISE

    def test_confidence_from_output(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.5)
        result = _result(True, {"confidence": 0.6})
        d = strategy.reflect(result, iteration=0)
        assert d.action == ReflectionAction.ACCEPT
        assert d.confidence == 0.6

    def test_confidence_default_one(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.9)
        result = _result(True, {})
        d = strategy.reflect(result, iteration=0)
        assert d.confidence == 1.0

    def test_confidence_clamped(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.5)
        result = _result(True, {"confidence": 1.5})
        d = strategy.reflect(result, iteration=0)
        assert d.confidence == 1.0
        result2 = _result(True, {"confidence": -0.5})
        d2 = strategy.reflect(result2, iteration=0)
        assert d2.confidence == 0.0

    def test_iteration_propagated(self):
        strategy = RuleBasedReflectionStrategy()
        d = strategy.reflect(_result(True, {"confidence": 0.9}), iteration=5)
        assert d.iteration == 5


class TestAlwaysRejectStrategy:
    def test_always_rejects(self):
        strategy = AlwaysRejectStrategy()
        d = strategy.reflect(_result(True, {}), iteration=0)
        assert d.action == ReflectionAction.REJECT


class TestReflectionAgent:
    def test_agent_abc(self):
        agent = ReflectionAgent(max_iterations=1)
        assert isinstance(agent, Agent)

    def test_status_restored(self):
        agent = ReflectionAgent(max_iterations=1)
        task = AgentTask(objective="reflect", input_data={"initial_result": _result(True, {"confidence": 0.9})})
        agent.run(task)
        assert agent.status == AgentStatus.IDLE

    def test_accept_immediate(self):
        agent = ReflectionAgent(max_iterations=3, min_confidence=0.7)
        result = _result(True, {"confidence": 0.9})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert r.success
        assert r.output.get("stopped_by") == "accept"

    def test_one_revision(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.9)
        agent = ReflectionAgent(strategy=strategy, max_iterations=3, min_confidence=0.9)
        result = _result(True, {"confidence": 0.5})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert r.success
        assert "_revised" in r.output.get("final", {})

    def test_max_iterations(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=1.0)
        agent = ReflectionAgent(strategy=strategy, max_iterations=3, min_confidence=1.0)
        result = _result(True, {"confidence": 0.5})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert r.success
        assert r.output.get("stopped_by") == "max_iterations"
        assert r.output.get("iterations") == 3

    def test_reject_stops(self):
        strategy = AlwaysRejectStrategy()
        agent = ReflectionAgent(strategy=strategy, max_iterations=5)
        result = _result(True, {"a": 1})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert not r.success
        assert r.output.get("stopped_by") == "reject"

    def test_no_initial_result(self):
        agent = ReflectionAgent(max_iterations=1)
        task = AgentTask(objective="reflect", input_data={})
        r = agent.run(task)
        assert not r.success
        assert "no_initial_result" in r.error

    def test_invalid_initial_result(self):
        agent = ReflectionAgent(max_iterations=1)
        task = AgentTask(objective="reflect", input_data={"initial_result": "not_an_agent_result"})
        r = agent.run(task)
        assert not r.success

    def test_strategy_swappable(self):
        agent = ReflectionAgent(max_iterations=1)
        assert isinstance(agent.strategy, RuleBasedReflectionStrategy)
        agent.strategy = AlwaysRejectStrategy()
        assert isinstance(agent.strategy, AlwaysRejectStrategy)

    def test_max_iterations_one(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.99)
        agent = ReflectionAgent(strategy=strategy, max_iterations=1, min_confidence=0.99)
        result = _result(True, {"confidence": 0.5})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert r.output.get("iterations") == 1

    def test_reflection_history(self):
        agent = ReflectionAgent(max_iterations=3, min_confidence=1.0)
        result = _result(True, {"confidence": 0.5})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert len(r.output.get("reflections", [])) > 0

    def test_last_decision_included(self):
        agent = ReflectionAgent(max_iterations=3, min_confidence=1.0)
        result = _result(True, {"confidence": 0.5})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert "final_decision" in r.output

    def test_reflect_on_direct(self):
        agent = ReflectionAgent()
        result = _result(True, {"confidence": 0.9})
        d = agent.reflect_on(result)
        assert isinstance(d, ReflectionDecision)
        assert d.action == ReflectionAction.ACCEPT

    def test_custom_strategy(self):
        class CustomStrategy(ReflectionStrategy):
            def reflect(self, result, iteration):
                return ReflectionDecision(action=ReflectionAction.ACCEPT, reason="custom", iteration=iteration)
        agent = ReflectionAgent(strategy=CustomStrategy(), max_iterations=1)
        result = _result(True, {"a": 1})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert r.success

    def test_confidence_edge_zero(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.5)
        result = _result(True, {"confidence": 0.0})
        d = strategy.reflect(result, iteration=0)
        assert d.action == ReflectionAction.REVISE

    def test_confidence_edge_one(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.99)
        result = _result(True, {"confidence": 1.0})
        d = strategy.reflect(result, iteration=0)
        assert d.action == ReflectionAction.ACCEPT

    def test_stop_action(self):
        class StopStrategy(ReflectionStrategy):
            def reflect(self, result, iteration):
                return ReflectionDecision(action=ReflectionAction.STOP, reason="stop", iteration=iteration)
        agent = ReflectionAgent(strategy=StopStrategy(), max_iterations=5)
        result = _result(True, {"a": 1})
        task = AgentTask(objective="reflect", input_data={"initial_result": result})
        r = agent.run(task)
        assert r.output.get("stopped_by") == "stop"

    def test_metadata_propagated(self):
        strategy = RuleBasedReflectionStrategy(min_confidence=0.5)
        result = _result(True, {"confidence": 0.9})
        d = strategy.reflect(result, iteration=2)
        assert d.metadata.get("confidence") == 0.9
        assert d.metadata.get("threshold") == 0.5

    def test_config_invalid_max_iterations(self):
        agent = ReflectionAgent(max_iterations=0)
        assert agent._max_iterations == 1  # clamped to min 1

    def test_config_invalid_min_confidence(self):
        agent = ReflectionAgent(min_confidence=-0.5)
        assert agent._min_confidence == 0.0
        agent2 = ReflectionAgent(min_confidence=1.5)
        assert agent2._min_confidence == 1.0


class TestThreadSafety:
    def test_concurrent_reflection(self):
        import concurrent.futures
        agent = ReflectionAgent(max_iterations=3, min_confidence=1.0)
        results = [_result(True, {"confidence": 0.5}) for _ in range(20)]
        tasks = [AgentTask(objective="reflect", input_data={"initial_result": r}) for r in results]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as exe:
            futures = [exe.submit(agent.run, t) for t in tasks]
            concurrent.futures.wait(futures)
        for f in futures:
            assert f.result().success
