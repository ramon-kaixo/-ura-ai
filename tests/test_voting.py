from __future__ import annotations

import pytest

from motor.intelligence.agents.consensus import (
    ConsensusResult,
    MajorityVoting,
    UnanimousVoting,
    VotingEngine,
    VotingStrategy,
)
from motor.intelligence.agents.message import AgentResult


def _result(success: bool, output: dict, agent_id: str = "") -> AgentResult:
    return AgentResult(task_id="t1", agent_id=agent_id, success=success, output=output)


class TestMajorityVoting:
    def test_unanimous_wins(self):
        results = [
            _result(True, {"answer": "cat"}, "a1"),
            _result(True, {"answer": "cat"}, "a2"),
            _result(True, {"answer": "cat"}, "a3"),
        ]
        r = MajorityVoting().aggregate(results)
        assert r.success
        assert r.outcome["answer"] == "cat"

    def test_majority_wins(self):
        results = [
            _result(True, {"answer": "cat"}, "a1"),
            _result(True, {"answer": "cat"}, "a2"),
            _result(True, {"answer": "dog"}, "a3"),
        ]
        r = MajorityVoting().aggregate(results)
        assert r.success
        assert r.outcome["answer"] == "cat"

    def test_tie_detected(self):
        results = [
            _result(True, {"answer": "cat"}, "a1"),
            _result(True, {"answer": "dog"}, "a2"),
        ]
        r = MajorityVoting().aggregate(results)
        assert not r.success
        assert r.outcome.get("_tie") is True

    def test_three_way_tie(self):
        results = [
            _result(True, {"answer": "cat"}, "a1"),
            _result(True, {"answer": "dog"}, "a2"),
            _result(True, {"answer": "bird"}, "a3"),
        ]
        r = MajorityVoting().aggregate(results)
        assert not r.success
        assert r.outcome.get("_tie") is True

    def test_empty_results(self):
        r = MajorityVoting().aggregate([])
        assert not r.success
        assert r.total_votes == 0

    def test_single_result(self):
        results = [_result(True, {"answer": "yes"})]
        r = MajorityVoting().aggregate(results)
        assert r.success
        assert r.outcome["answer"] == "yes"

    def test_vote_counts(self):
        results = [
            _result(True, {"a": 1}, "a1"),
            _result(True, {"a": 1}, "a2"),
            _result(True, {"a": 2}, "a3"),
        ]
        r = MajorityVoting().aggregate(results)
        total = sum(r.vote_counts.values())
        assert total == 3

    def test_tie_with_error(self):
        r1 = AgentResult(task_id="t1", agent_id="a1", success=True, output={"ok": True})
        r2 = AgentResult(task_id="t1", agent_id="a2", success=False, error="fail")
        r = MajorityVoting().aggregate([r1, r2])
        assert not r.success  # tie between ok and fail


class TestUnanimousVoting:
    def test_all_agree(self):
        results = [
            _result(True, {"x": 1}, "a1"),
            _result(True, {"x": 1}, "a2"),
        ]
        r = UnanimousVoting().aggregate(results)
        assert r.success
        assert r.outcome["x"] == 1

    def test_one_disagrees(self):
        results = [
            _result(True, {"x": 1}, "a1"),
            _result(True, {"x": 2}, "a2"),
        ]
        r = UnanimousVoting().aggregate(results)
        assert not r.success
        assert r.outcome.get("_unanimous_failed") is True

    def test_single_result(self):
        results = [_result(True, {"x": 1})]
        r = UnanimousVoting().aggregate(results)
        assert r.success

    def test_empty(self):
        r = UnanimousVoting().aggregate([])
        assert not r.success


class TestVotingStrategyABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            VotingStrategy()


class TestVotingEngine:
    def test_default_strategy(self):
        engine = VotingEngine()
        assert engine.strategy.name() == "majority"

    def test_strategy_swappable(self):
        engine = VotingEngine()
        engine.strategy = UnanimousVoting()
        assert engine.strategy.name() == "unanimous"

    def test_vote_with_majority(self):
        engine = VotingEngine()
        engine.register_strategy(MajorityVoting())
        results = [
            _result(True, {"a": 1}, "a1"),
            _result(True, {"a": 1}, "a2"),
        ]
        r = engine.vote_with(results, "majority")
        assert r.success

    def test_vote_with_unknown_raises(self):
        engine = VotingEngine()
        with pytest.raises(ValueError, match="Unknown strategy"):
            engine.vote_with([], "nonexistent")

    def test_register_and_get(self):
        engine = VotingEngine()
        engine.register_strategy(MajorityVoting())
        s = engine.get_strategy("majority")
        assert s is not None
        assert s.name() == "majority"

    def test_get_nonexistent(self):
        engine = VotingEngine()
        assert engine.get_strategy("nope") is None


class TestConsensusResult:
    def test_vote_summary(self):
        r = ConsensusResult(
            success=True, outcome={}, votes=[],
            vote_counts={"a": 3, "b": 1}, total_votes=4,
            strategy="majority",
        )
        assert "3" in r.vote_summary
        assert "majority" in r.vote_summary
