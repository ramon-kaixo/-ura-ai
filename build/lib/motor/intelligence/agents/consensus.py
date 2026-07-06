"""VotingEngine — estrategias de votación para consenso entre agentes."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from motor.intelligence.agents.message import AgentResult


@dataclass
class ConsensusResult:
    success: bool
    outcome: dict[str, Any]
    votes: list[AgentResult]
    vote_counts: dict[str, int]
    total_votes: int
    strategy: str
    weighted: bool = False
    weight_details: dict[str, float] | None = None

    @property
    def vote_summary(self) -> str:
        return f"{self.strategy}: {self.vote_counts} ({self.total_votes} votes)"


class VotingStrategy(ABC):
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def aggregate(self, results: list[AgentResult]) -> ConsensusResult:
        ...


class MajorityVoting(VotingStrategy):
    def name(self) -> str:
        return "majority"

    def aggregate(self, results: list[AgentResult]) -> ConsensusResult:
        if not results:
            return ConsensusResult(
                success=False, outcome={}, votes=[], vote_counts={},
                total_votes=0, strategy=self.name(),
            )
        tally: dict[str, list[AgentResult]] = {}
        for r in results:
            key = self._result_key(r)
            tally.setdefault(key, []).append(r)

        max_count = max(len(v) for v in tally.values())
        winners = [k for k, v in tally.items() if len(v) == max_count]

        vote_counts = {k: len(v) for k, v in tally.items()}
        total = len(results)

        if len(winners) == 1:
            winner_key = winners[0]
            outcome = tally[winner_key][0].output
            return ConsensusResult(
                success=True, outcome=outcome, votes=results,
                vote_counts=vote_counts, total_votes=total,
                strategy=self.name(),
            )
        if len(winners) > 1:
            tie_key = winners[0]
            outcome = tally[tie_key][0].output
            outcome["_tie"] = True
            outcome["_tied_keys"] = winners
            return ConsensusResult(
                success=False, outcome=outcome, votes=results,
                vote_counts=vote_counts, total_votes=total,
                strategy=self.name(),
            )
        return ConsensusResult(
            success=False, outcome={}, votes=results,
            vote_counts=vote_counts, total_votes=total,
            strategy=self.name(),
        )

    def _result_key(self, r: AgentResult) -> str:
        return str(sorted(r.output.items())) if r.output else f"error:{r.error}"


class UnanimousVoting(VotingStrategy):
    def name(self) -> str:
        return "unanimous"

    def aggregate(self, results: list[AgentResult]) -> ConsensusResult:
        if not results:
            return ConsensusResult(
                success=False, outcome={}, votes=[], vote_counts={},
                total_votes=0, strategy=self.name(),
            )
        if len(results) == 1:
            return ConsensusResult(
                success=True, outcome=results[0].output, votes=results,
                vote_counts={self._result_key(results[0]): 1},
                total_votes=1, strategy=self.name(),
            )
        first_key = self._result_key(results[0])
        tally: dict[str, list[AgentResult]] = {}
        for r in results:
            key = self._result_key(r)
            tally.setdefault(key, []).append(r)

        vote_counts = {k: len(v) for k, v in tally.items()}
        is_unanimous = len(tally) == 1

        if is_unanimous:
            return ConsensusResult(
                success=True, outcome=results[0].output, votes=results,
                vote_counts=vote_counts, total_votes=len(results),
                strategy=self.name(),
            )
        outcome = {"_tie": True, "_unanimous_failed": True, "_vote_groups": len(tally)}
        return ConsensusResult(
            success=False, outcome=outcome, votes=results,
            vote_counts=vote_counts, total_votes=len(results),
            strategy=self.name(),
        )

    def _result_key(self, r: AgentResult) -> str:
        return str(sorted(r.output.items())) if r.output else f"error:{r.error}"


class VotingEngine:
    def __init__(self, strategy: VotingStrategy | None = None) -> None:
        self._strategy = strategy or MajorityVoting()
        self._strategies: dict[str, VotingStrategy] = {}

    @property
    def strategy(self) -> VotingStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, new_strategy: VotingStrategy) -> None:
        self._strategy = new_strategy

    def register_strategy(self, strategy: VotingStrategy) -> None:
        self._strategies[strategy.name()] = strategy

    def get_strategy(self, name: str) -> VotingStrategy | None:
        return self._strategies.get(name)

    def vote(self, results: list[AgentResult]) -> ConsensusResult:
        return self._strategy.aggregate(results)

    def vote_with(self, results: list[AgentResult], strategy_name: str) -> ConsensusResult:
        strategy = self._strategies.get(strategy_name)
        if strategy is None:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        return strategy.aggregate(results)


def normalized_confidence(result: AgentResult) -> float:
    conf = result.output.get("confidence", 1.0) if result.output else 1.0
    if not isinstance(conf, (int, float)):
        return 1.0
    return max(0.0, min(1.0, float(conf)))


class AgentWeightRegistry:
    def __init__(self) -> None:
        self._weights: dict[str, float] = {}
        self._lock = threading.RLock()

    def set_weight(self, agent_id: str, weight: float) -> None:
        with self._lock:
            self._weights[agent_id] = max(0.0, weight)

    def get_weight(self, agent_id: str) -> float:
        with self._lock:
            return self._weights.get(agent_id, 1.0)

    def reset(self) -> None:
        with self._lock:
            self._weights.clear()

    def reset_agent(self, agent_id: str) -> bool:
        with self._lock:
            return self._weights.pop(agent_id, None) is not None

    def all_weights(self) -> dict[str, float]:
        with self._lock:
            return dict(self._weights)


class WeightedConsensus(VotingStrategy):
    def __init__(self, weight_registry: AgentWeightRegistry | None = None) -> None:
        self._registry = weight_registry or AgentWeightRegistry()

    @property
    def registry(self) -> AgentWeightRegistry:
        return self._registry

    def name(self) -> str:
        return "weighted"

    def aggregate(self, results: list[AgentResult]) -> ConsensusResult:
        if not results:
            return ConsensusResult(
                success=False, outcome={}, votes=[], vote_counts={},
                total_votes=0, strategy=self.name(), weighted=True,
            )

        tally: dict[str, float] = {}
        weight_details: dict[str, float] = {}

        for r in results:
            key = self._result_key(r)
            weight = self._registry.get_weight(r.agent_id)
            conf = normalized_confidence(r)
            effective = weight * conf
            tally[key] = tally.get(key, 0.0) + effective
            weight_details[r.agent_id] = effective

        max_weight = max(tally.values())
        winners = [k for k, v in tally.items() if v == max_weight]

        vote_counts = {k: round(v, 4) for k, v in tally.items()}
        total = len(results)

        if len(winners) == 1:
            winner_key = winners[0]
            for r in results:
                if self._result_key(r) == winner_key:
                    outcome = dict(r.output)
                    break
            else:
                outcome = {}
            return ConsensusResult(
                success=True, outcome=outcome, votes=results,
                vote_counts=vote_counts, total_votes=total,
                strategy=self.name(), weighted=True,
                weight_details=weight_details,
            )

        if len(winners) > 1:
            for r in results:
                if self._result_key(r) == winners[0]:
                    outcome = dict(r.output)
                    break
            else:
                outcome = {}
            outcome["_tie"] = True
            outcome["_tied_keys"] = winners
            return ConsensusResult(
                success=False, outcome=outcome, votes=results,
                vote_counts=vote_counts, total_votes=total,
                strategy=self.name(), weighted=True,
                weight_details=weight_details,
            )

        return ConsensusResult(
            success=False, outcome={}, votes=results,
            vote_counts=vote_counts, total_votes=total,
            strategy=self.name(), weighted=True,
            weight_details=weight_details,
        )

    def _result_key(self, r: AgentResult) -> str:
        return str(sorted(r.output.items())) if r.output else f"error:{r.error}"
