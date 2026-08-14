"""Tests para motor.intelligence.agents.consensus (VotingEngine, estrategias)."""
from __future__ import annotations

import pytest

from motor.intelligence.agents.consensus import (
    AgentWeightRegistry,
    ConsensusResult,
    MajorityVoting,
    UnanimousVoting,
    VotingEngine,
    VotingStrategy,
    WeightedConsensus,
    _mayoria,
    _outcome_para,
    normalized_confidence,
)
from motor.intelligence.agents.message import AgentResult


def _result(agent_id: str, output: dict | None = None, error: str = "") -> AgentResult:
    return AgentResult(
        task_id="t1",
        agent_id=agent_id,
        success=not error,
        output=output or {},
        error=error,
    )


class TestConsensusResult:
    def test_vote_summary(self):
        result = ConsensusResult(
            success=True,
            outcome={},
            votes=[],
            vote_counts={"a": 2},
            total_votes=2,
            strategy="majority",
        )
        assert result.vote_summary == "majority: {'a': 2} (2 votes)"


class TestMajorityVoting:
    def test_name(self):
        assert MajorityVoting().name() == "majority"

    def test_empty_results(self):
        result = MajorityVoting().aggregate([])
        assert result.success is False
        assert result.outcome == {}
        assert result.total_votes == 0

    def test_single_winner(self):
        results = [
            _result("a1", {"ans": 1}),
            _result("a2", {"ans": 1}),
            _result("a3", {"ans": 2}),
        ]
        result = MajorityVoting().aggregate(results)
        assert result.success is True
        assert result.outcome == {"ans": 1}
        assert result.vote_counts == {"[('ans', 1)]": 2, "[('ans', 2)]": 1}
        assert result.total_votes == 3

    def test_tie(self):
        results = [
            _result("a1", {"ans": 1}),
            _result("a2", {"ans": 2}),
        ]
        result = MajorityVoting().aggregate(results)
        assert result.success is False
        assert result.outcome["_tie"] is True
        assert len(result.outcome["_tied_keys"]) == 2

    def test_result_key_error_output(self):
        results = [_result("a1", error="boom")]
        result = MajorityVoting().aggregate(results)
        assert result.vote_counts == {"error:boom": 1}

    def test_result_key_empty_output(self):
        r = _result("a1", None)
        assert MajorityVoting()._result_key(r) == "error:"


class TestUnanimousVoting:
    def test_name(self):
        assert UnanimousVoting().name() == "unanimous"

    def test_empty_results(self):
        result = UnanimousVoting().aggregate([])
        assert result.success is False
        assert result.total_votes == 0

    def test_single_result_succeeds(self):
        result = UnanimousVoting().aggregate([_result("a1", {"ans": 1})])
        assert result.success is True
        assert result.total_votes == 1

    def test_unanimous(self):
        results = [
            _result("a1", {"ans": 1}),
            _result("a2", {"ans": 1}),
        ]
        result = UnanimousVoting().aggregate(results)
        assert result.success is True
        assert result.outcome == {"ans": 1}
        assert len(result.vote_counts) == 1

    def test_not_unanimous(self):
        results = [
            _result("a1", {"ans": 1}),
            _result("a2", {"ans": 2}),
        ]
        result = UnanimousVoting().aggregate(results)
        assert result.success is False
        assert result.outcome["_unanimous_failed"] is True
        assert len(result.vote_counts) == 2


class TestVotingEngine:
    def test_default_strategy_majority(self):
        engine = VotingEngine()
        assert isinstance(engine.strategy, MajorityVoting)

    def test_strategy_setter(self):
        engine = VotingEngine()
        strategy = UnanimousVoting()
        engine.strategy = strategy
        assert engine.strategy is strategy

    def test_register_and_get(self):
        engine = VotingEngine()
        engine.register_strategy(UnanimousVoting())
        assert isinstance(engine.get_strategy("unanimous"), UnanimousVoting)
        assert engine.get_strategy("nope") is None

    def test_vote_uses_current_strategy(self):
        engine = VotingEngine(strategy=UnanimousVoting())
        result = engine.vote([_result("a1", {"ans": 1})])
        assert result.success is True
        assert result.strategy == "unanimous"

    def test_vote_with(self):
        engine = VotingEngine()
        engine.register_strategy(UnanimousVoting())
        result = engine.vote_with([_result("a1", {"ans": 1})], "unanimous")
        assert result.success is True

    def test_vote_with_unknown_raises(self):
        engine = VotingEngine()
        with pytest.raises(ValueError, match="Unknown strategy"):
            engine.vote_with([], "nope")


class TestNormalizedConfidence:
    def test_default_when_no_output(self):
        result = _result("a1", None)
        assert normalized_confidence(result) == 1.0

    def test_uses_confidence(self):
        result = _result("a1", {"confidence": 0.4})
        assert normalized_confidence(result) == 0.4

    def test_clamps_bounds(self):
        assert normalized_confidence(_result("a1", {"confidence": 5.0})) == 1.0
        assert normalized_confidence(_result("a1", {"confidence": -2.0})) == 0.0

    def test_non_numeric_returns_one(self):
        assert normalized_confidence(_result("a1", {"confidence": "alto"})) == 1.0


class TestAgentWeightRegistry:
    def test_default_weight(self):
        registry = AgentWeightRegistry()
        assert registry.get_weight("a1") == 1.0

    def test_set_and_get(self):
        registry = AgentWeightRegistry()
        registry.set_weight("a1", 2.0)
        assert registry.get_weight("a1") == 2.0

    def test_set_clamps_negative(self):
        registry = AgentWeightRegistry()
        registry.set_weight("a1", -5.0)
        assert registry.get_weight("a1") == 0.0

    def test_reset(self):
        registry = AgentWeightRegistry()
        registry.set_weight("a1", 2.0)
        registry.reset()
        assert registry.all_weights() == {}

    def test_reset_agent(self):
        registry = AgentWeightRegistry()
        registry.set_weight("a1", 2.0)
        assert registry.reset_agent("a1") is True
        assert registry.reset_agent("a1") is False

    def test_all_weights_copy(self):
        registry = AgentWeightRegistry()
        registry.set_weight("a1", 1.5)
        weights = registry.all_weights()
        weights["a1"] = 99.0
        assert registry.get_weight("a1") == 1.5


class TestWeightedConsensus:
    def test_name(self):
        assert WeightedConsensus().name() == "weighted"

    def test_default_registry(self):
        assert isinstance(WeightedConsensus().registry, AgentWeightRegistry)

    def test_empty_results(self):
        result = WeightedConsensus().aggregate([])
        assert result.success is False
        assert result.weighted is True
        assert result.total_votes == 0

    def test_winner_weighted(self):
        registry = AgentWeightRegistry()
        registry.set_weight("a1", 3.0)
        strategy = WeightedConsensus(registry)
        results = [
            _result("a1", {"ans": 1}),
            _result("a2", {"ans": 2}),
        ]
        result = strategy.aggregate(results)
        assert result.success is True
        assert result.outcome == {"ans": 1}
        assert result.weight_details["a1"] == 3.0
        assert result.weight_details["a2"] == 1.0

    def test_confidence_multiplies_weight(self):
        registry = AgentWeightRegistry()
        registry.set_weight("a1", 2.0)
        strategy = WeightedConsensus(registry)
        results = [_result("a1", {"ans": 1, "confidence": 0.5})]
        result = strategy.aggregate(results)
        assert result.success is True
        assert result.weight_details["a1"] == 1.0

    def test_tie(self):
        registry = AgentWeightRegistry()
        registry.set_weight("a1", 1.0)
        strategy = WeightedConsensus(registry)
        results = [
            _result("a1", {"ans": 1}),
            _result("a2", {"ans": 2}),
        ]
        result = strategy.aggregate(results)
        assert result.success is False
        assert result.outcome["_tie"] is True

    def test_error_result_key(self):
        strategy = WeightedConsensus()
        result = strategy.aggregate([_result("a1", error="boom")])
        assert result.success is True
        assert result.vote_counts == {"error:boom": 1.0}

    def test_outcome_para_no_match_returns_empty(self):
        results = [_result("a1", {"ans": 1})]
        strategy = WeightedConsensus()
        # Comportamiento desde TASK-20260814-001 (commit e63fd4d2): rama inalcanzable
        # por construccion (winner_key siempre en keys(tally)), fail-fast en vez de {} silencioso.
        with pytest.raises(AssertionError, match="winner key"):
            _outcome_para("no-existe", results, strategy)


class TestHelpers:
    def test_mayoria_single(self):
        assert _mayoria({"a": 1.0, "b": 0.5}) == ["a"]

    def test_mayoria_tie(self):
        assert sorted(_mayoria({"a": 1.0, "b": 1.0})) == ["a", "b"]

    def test_mayoria_empty(self):
        with pytest.raises(ValueError):
            _mayoria({})

    def test_outcome_para_matches(self):
        results = [_result("a1", {"ans": 1}), _result("a2", {"ans": 2})]
        strategy = WeightedConsensus()
        key = strategy._result_key(results[0])
        assert _outcome_para(key, results, strategy) == {"ans": 1}


class TestStrategyRegistration:
    def test_custom_strategy(self):
        class Custom(VotingStrategy):
            def name(self) -> str:
                return "custom"

            def aggregate(self, results):
                return ConsensusResult(
                    success=True,
                    outcome={"custom": True},
                    votes=results,
                    vote_counts={},
                    total_votes=len(results),
                    strategy=self.name(),
                )

        engine = VotingEngine()
        engine.register_strategy(Custom())
        result = engine.vote_with([_result("a1")], "custom")
        assert result.success is True
        assert result.outcome == {"custom": True}
