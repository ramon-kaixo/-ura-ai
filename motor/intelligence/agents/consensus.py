"""VotingEngine — estrategias de votación para consenso entre agentes."""

from __future__ import annotations

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
