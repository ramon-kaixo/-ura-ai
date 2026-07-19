from __future__ import annotations

from motor.intelligence.agents.consensus import (
    AgentWeightRegistry,
    ConsensusResult,
    MajorityVoting,
    UnanimousVoting,
    VotingEngine,
    WeightedConsensus,
    normalized_confidence,
)
from motor.intelligence.agents.message import AgentResult


def _r(success: bool, output: dict, agent_id: str = "") -> AgentResult:  # noqa: FBT001
    return AgentResult(task_id="t1", agent_id=agent_id, success=success, output=output)


class TestNormalizedConfidence:
    def test_default_one(self):
        r = _r(True, {"ok": True})  # noqa: FBT003
        assert normalized_confidence(r) == 1.0

    def test_from_output(self):
        r = _r(True, {"confidence": 0.7})  # noqa: FBT003
        assert normalized_confidence(r) == 0.7

    def test_clamps_low(self):
        r = _r(True, {"confidence": -0.5})  # noqa: FBT003
        assert normalized_confidence(r) == 0.0

    def test_clamps_high(self):
        r = _r(True, {"confidence": 1.5})  # noqa: FBT003
        assert normalized_confidence(r) == 1.0

    def test_non_numeric(self):
        r = _r(True, {"confidence": "high"})  # noqa: FBT003
        assert normalized_confidence(r) == 1.0

    def test_empty_output(self):
        r = AgentResult(task_id="t1", agent_id="a1", success=True, output={})
        assert normalized_confidence(r) == 1.0


class TestAgentWeightRegistry:
    def test_default_weight(self):
        reg = AgentWeightRegistry()
        assert reg.get_weight("a1") == 1.0

    def test_set_weight(self):
        reg = AgentWeightRegistry()
        reg.set_weight("a1", 2.5)
        assert reg.get_weight("a1") == 2.5

    def test_negative_weight_clamped(self):
        reg = AgentWeightRegistry()
        reg.set_weight("a1", -1.0)
        assert reg.get_weight("a1") == 0.0

    def test_reset(self):
        reg = AgentWeightRegistry()
        reg.set_weight("a1", 3.0)
        reg.reset()
        assert reg.get_weight("a1") == 1.0

    def test_reset_agent(self):
        reg = AgentWeightRegistry()
        reg.set_weight("a1", 3.0)
        assert reg.reset_agent("a1") is True
        assert reg.get_weight("a1") == 1.0

    def test_reset_nonexistent(self):
        reg = AgentWeightRegistry()
        assert reg.reset_agent("nobody") is False

    def test_all_weights(self):
        reg = AgentWeightRegistry()
        reg.set_weight("a1", 2.0)
        reg.set_weight("a2", 3.0)
        w = reg.all_weights()
        assert w["a1"] == 2.0
        assert w["a2"] == 3.0

    def test_thread_safety(self):
        import concurrent.futures

        reg = AgentWeightRegistry()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as exe:
            futures = [exe.submit(reg.set_weight, f"a{i}", float(i)) for i in range(100)]
            concurrent.futures.wait(futures)
        assert reg.get_weight("a50") == 50.0


class TestWeightedConsensus:
    def test_equal_weights(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        reg.set_weight("a1", 1.0)
        reg.set_weight("a2", 1.0)
        results = [
            _r(True, {"answer": "cat"}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "cat"}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert r.success
        assert r.outcome["answer"] == "cat"

    def test_different_weights(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        reg.set_weight("a1", 5.0)
        reg.set_weight("a2", 1.0)
        results = [
            _r(True, {"answer": "cat"}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "dog"}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert r.success
        assert r.outcome["answer"] == "cat"

    def test_high_confidence(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        reg.set_weight("a1", 1.0)
        reg.set_weight("a2", 1.0)
        results = [
            _r(True, {"answer": "cat", "confidence": 0.9}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "dog", "confidence": 0.1}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert r.success
        assert r.outcome["answer"] == "cat"

    def test_low_confidence(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        reg.set_weight("a1", 1.0)
        reg.set_weight("a2", 1.0)
        results = [
            _r(True, {"answer": "cat", "confidence": 0.1}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "dog", "confidence": 0.9}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert r.success
        assert r.outcome["answer"] == "dog"

    def test_confidence_absent_defaults_one(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        results = [
            _r(True, {"answer": "cat"}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "cat"}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert r.success

    def test_weighted_tie(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        reg.set_weight("a1", 2.0)
        reg.set_weight("a2", 2.0)
        results = [
            _r(True, {"answer": "cat"}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "dog"}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert not r.success
        assert r.outcome.get("_tie") is True

    def test_zero_weight(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        reg.set_weight("a1", 0.0)
        reg.set_weight("a2", 1.0)
        results = [
            _r(True, {"answer": "cat"}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "dog"}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert r.success
        assert r.outcome["answer"] == "dog"

    def test_dynamic_weight_update(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        reg.set_weight("a1", 10.0)
        reg.set_weight("a2", 1.0)
        results = [
            _r(True, {"answer": "cat"}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "dog"}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert r.outcome["answer"] == "cat"
        reg.set_weight("a1", 0.5)
        r2 = wc.aggregate(results)
        assert r2.outcome["answer"] == "dog"

    def test_multiple_agents(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        agents = [(f"a{i}", 1.0, i % 3) for i in range(10)]
        for aid, w, _val in agents:
            reg.set_weight(aid, w)
        results = [_r(True, {"val": val}, aid) for aid, _, val in agents]  # noqa: FBT003
        r = wc.aggregate(results)
        assert r.success  # 4 agents voted for 0, 3 for 1, 3 for 2

    def test_empty(self):
        wc = WeightedConsensus()
        r = wc.aggregate([])
        assert not r.success
        assert r.total_votes == 0

    def test_weight_details_in_result(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        reg.set_weight("a1", 2.0)
        reg.set_weight("a2", 1.0)
        results = [
            _r(True, {"answer": "x"}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "y"}, "a2"),  # noqa: FBT003
        ]
        r = wc.aggregate(results)
        assert r.weight_details is not None
        assert r.weight_details["a1"] == 2.0


class TestWeightedCompatibility:
    def test_via_voting_engine(self):
        engine = VotingEngine()
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        engine.register_strategy(wc)
        reg.set_weight("a1", 3.0)
        reg.set_weight("a2", 1.0)
        results = [
            _r(True, {"answer": "cat"}, "a1"),  # noqa: FBT003
            _r(True, {"answer": "dog"}, "a2"),  # noqa: FBT003
        ]
        r = engine.vote_with(results, "weighted")
        assert r.success
        assert r.weighted

    def test_majority_still_works(self):
        engine = VotingEngine()
        engine.strategy = MajorityVoting()
        results = [
            _r(True, {"a": 1}, "a1"),  # noqa: FBT003
            _r(True, {"a": 2}, "a2"),  # noqa: FBT003
        ]
        r = engine.vote(results)
        assert not r.success  # tie
        assert not r.weighted

    def test_unanimous_still_works(self):
        engine = VotingEngine()
        engine.strategy = UnanimousVoting()
        results = [
            _r(True, {"a": 1}, "a1"),  # noqa: FBT003
            _r(True, {"a": 1}, "a2"),  # noqa: FBT003
        ]
        r = engine.vote(results)
        assert r.success
        assert not r.weighted

    def test_registry_from_engine(self):
        reg = AgentWeightRegistry()
        wc = WeightedConsensus(reg)
        assert wc.registry is reg


class TestConsensusResultExtended:
    def test_weighted_flag(self):
        r = ConsensusResult(
            success=True,
            outcome={},
            votes=[],
            vote_counts={},
            total_votes=0,
            strategy="weighted",
            weighted=True,
        )
        assert r.weighted


# ── Legacy tests (must remain passing) ─────────────────────────────────────


class _helper:
    @staticmethod
    def result(success: bool, output: dict, agent_id: str = "") -> AgentResult:  # noqa: FBT001
        return AgentResult(task_id="t1", agent_id=agent_id, success=success, output=output)


class TestMajorityVotingLegacy:
    def test_unanimous_wins(self):
        r = MajorityVoting().aggregate(
            [
                _helper.result(True, {"a": 1}),  # noqa: FBT003
                _helper.result(True, {"a": 1}),  # noqa: FBT003
            ],
        )
        assert r.success

    def test_majority_wins(self):
        r = MajorityVoting().aggregate(
            [
                _helper.result(True, {"a": 1}),  # noqa: FBT003
                _helper.result(True, {"a": 1}),  # noqa: FBT003
                _helper.result(True, {"a": 2}),  # noqa: FBT003
            ],
        )
        assert r.success

    def test_tie_detected(self):
        r = MajorityVoting().aggregate(
            [
                _helper.result(True, {"a": 1}),  # noqa: FBT003
                _helper.result(True, {"a": 2}),  # noqa: FBT003
            ],
        )
        assert not r.success
        assert r.outcome.get("_tie") is True

    def test_empty(self):
        r = MajorityVoting().aggregate([])
        assert not r.success

    def test_single(self):
        r = MajorityVoting().aggregate([_helper.result(True, {"a": 1})])  # noqa: FBT003
        assert r.success


class TestUnanimousVotingLegacy:
    def test_all_agree(self):
        r = UnanimousVoting().aggregate(
            [
                _helper.result(True, {"a": 1}),  # noqa: FBT003
                _helper.result(True, {"a": 1}),  # noqa: FBT003
            ],
        )
        assert r.success

    def test_disagrees(self):
        r = UnanimousVoting().aggregate(
            [
                _helper.result(True, {"a": 1}),  # noqa: FBT003
                _helper.result(True, {"a": 2}),  # noqa: FBT003
            ],
        )
        assert not r.success

    def test_single(self):
        r = UnanimousVoting().aggregate([_helper.result(True, {"a": 1})])  # noqa: FBT003
        assert r.success


class TestVotingEngineLegacy:
    def test_default_majority(self):
        assert VotingEngine().strategy.name() == "majority"

    def test_swap_strategy(self):
        e = VotingEngine()
        e.strategy = UnanimousVoting()
        assert e.strategy.name() == "unanimous"

    def test_register_and_vote(self):
        e = VotingEngine()
        e.register_strategy(MajorityVoting())
        r = e.vote_with([_helper.result(True, {"a": 1}), _helper.result(True, {"a": 1})], "majority")  # noqa: FBT003
        assert r.success

    def test_unknown_raises(self):
        import pytest

        with pytest.raises(ValueError):
            VotingEngine().vote_with([], "nope")
