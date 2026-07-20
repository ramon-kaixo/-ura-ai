"""ReflectionAgent — agente de reflexión desacoplado del runtime."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentRole, AgentStatus, AgentTask

log = logging.getLogger("ura.agent.reflection")


class ReflectionAction(Enum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"
    STOP = "stop"


@dataclass
class ReflectionDecision:
    action: ReflectionAction = ReflectionAction.ACCEPT
    confidence: float = 1.0
    reason: str = ""
    iteration: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ReflectionStrategy(ABC):
    @abstractmethod
    def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision: ...


class RuleBasedReflectionStrategy(ReflectionStrategy):
    def __init__(self, min_confidence: float = 0.7) -> None:
        self._min_confidence = min_confidence

    def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
        if not result.success:
            return ReflectionDecision(
                action=ReflectionAction.REVISE,
                confidence=0.0,
                reason="result_indicates_failure",
                iteration=iteration,
                metadata={"result_error": result.error, "iteration": iteration},
            )
        confidence = result.output.get("confidence", 1.0) if result.output else 1.0
        confidence = max(0.0, min(1.0, float(confidence))) if isinstance(confidence, (int, float)) else 1.0
        if confidence >= self._min_confidence:
            return ReflectionDecision(
                action=ReflectionAction.ACCEPT,
                confidence=confidence,
                reason=f"confidence_{confidence:.2f}_above_threshold_{self._min_confidence:.2f}",
                iteration=iteration,
                metadata={"confidence": confidence, "threshold": self._min_confidence},
            )
        return ReflectionDecision(
            action=ReflectionAction.REVISE,
            confidence=confidence,
            reason=f"confidence_{confidence:.2f}_below_threshold_{self._min_confidence:.2f}",
            iteration=iteration,
            metadata={"confidence": confidence, "threshold": self._min_confidence},
        )


class AlwaysRejectStrategy(ReflectionStrategy):
    def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
        return ReflectionDecision(
            action=ReflectionAction.REJECT,
            confidence=0.0,
            reason="always_reject",
            iteration=iteration,
        )


class ReflectionAgent(Agent):
    def __init__(
        self,
        strategy: ReflectionStrategy | None = None,
        max_iterations: int = 3,
        min_confidence: float = 0.90,
        stop_on_accept: bool = True,
        agent_id: str = "",
    ) -> None:
        self.id = agent_id or uuid.uuid4().hex[:12]
        self.name = "reflection"
        self.role = AgentRole.VALIDATOR
        self.capabilities = ["reflect", "review", "critique"]
        self.status = AgentStatus.IDLE
        self._strategy = strategy or RuleBasedReflectionStrategy(min_confidence=min_confidence)
        self._max_iterations = max(1, max_iterations)
        self._min_confidence = max(0.0, min(1.0, min_confidence))
        self._stop_on_accept = stop_on_accept
        self._lock = threading.Lock()

    @property
    def strategy(self) -> ReflectionStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, new_strategy: ReflectionStrategy) -> None:
        self._strategy = new_strategy

    def run(self, task: AgentTask) -> AgentResult:
        start = time.monotonic()
        self.status = AgentStatus.BUSY
        try:
            result = self._reflect(task)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=result.success,
                output=result.output,
                error=result.error,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as exc:
            log.warning("ReflectionAgent error: %s", exc)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )
        finally:
            self.status = AgentStatus.IDLE

    def reflect_on(self, result: AgentResult) -> ReflectionDecision:
        return self._strategy.reflect(result, iteration=0)

    def _reflect(self, task: AgentTask) -> AgentResult:  # noqa: PLR0911
        initial = task.input_data.get("initial_result")
        if initial is None:
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                output={},
                error="no_initial_result_provided",
            )
        if not isinstance(initial, AgentResult):
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                output={},
                error="initial_result_not_agent_result",
            )

        history: list[ReflectionDecision] = []
        current = initial

        for iteration in range(self._max_iterations + 1):
            decision = self._strategy.reflect(current, iteration)
            history.append(decision)

            if decision.action == ReflectionAction.STOP:
                return AgentResult(
                    task_id=task.id,
                    agent_id=self.id,
                    success=current.success,
                    output={
                        "final": current.output,
                        "reflections": [self._decision_to_dict(d) for d in history],
                        "final_decision": self._decision_to_dict(decision),
                        "reason": decision.reason,
                        "iterations": iteration,
                        "stopped_by": "stop",
                    },
                )

            if decision.action == ReflectionAction.ACCEPT and self._stop_on_accept:
                return AgentResult(
                    task_id=task.id,
                    agent_id=self.id,
                    success=current.success,
                    output={
                        "final": current.output,
                        "reflections": [self._decision_to_dict(d) for d in history],
                        "final_decision": self._decision_to_dict(decision),
                        "reason": decision.reason,
                        "iterations": iteration,
                        "stopped_by": "accept",
                    },
                )

            if decision.action == ReflectionAction.ACCEPT and decision.confidence >= self._min_confidence:
                return AgentResult(
                    task_id=task.id,
                    agent_id=self.id,
                    success=current.success,
                    output={
                        "final": current.output,
                        "reflections": [self._decision_to_dict(d) for d in history],
                        "final_decision": self._decision_to_dict(decision),
                        "reason": decision.reason,
                        "iterations": iteration,
                        "stopped_by": "confidence",
                    },
                )

            if decision.action == ReflectionAction.REJECT:
                return AgentResult(
                    task_id=task.id,
                    agent_id=self.id,
                    success=False,
                    output={
                        "final": current.output,
                        "reflections": [self._decision_to_dict(d) for d in history],
                        "final_decision": self._decision_to_dict(decision),
                        "reason": decision.reason,
                        "iterations": iteration,
                        "stopped_by": "reject",
                    },
                )

            if decision.action == ReflectionAction.REVISE:
                revised = self._revise(current, decision)
                if revised is None:
                    return AgentResult(
                        task_id=task.id,
                        agent_id=self.id,
                        success=current.success,
                        output={
                            "final": current.output,
                            "reflections": [self._decision_to_dict(d) for d in history],
                            "final_decision": self._decision_to_dict(decision),
                            "reason": "revise_failed_no_new_result",
                            "iterations": iteration,
                            "stopped_by": "revise_failed",
                        },
                    )
                current = revised

        final_decision = history[-1] if history else ReflectionDecision(reason="max_iterations_reached")
        return AgentResult(
            task_id=task.id,
            agent_id=self.id,
            success=current.success,
            output={
                "final": current.output,
                "reflections": [self._decision_to_dict(d) for d in history],
                "final_decision": self._decision_to_dict(final_decision),
                "reason": "max_iterations",
                "iterations": self._max_iterations,
                "stopped_by": "max_iterations",
            },
        )

    def _revise(self, result: AgentResult, decision: ReflectionDecision) -> AgentResult | None:
        revised_output = dict(result.output) if result.output else {}
        revised_output["_revised"] = True
        revised_output["_revision_reason"] = decision.reason
        revised_output["_revision_iteration"] = decision.iteration
        return AgentResult(
            task_id=result.task_id,
            agent_id=result.agent_id,
            success=result.success,
            output=revised_output,
        )

    def _decision_to_dict(self, d: ReflectionDecision) -> dict[str, Any]:
        return {
            "action": d.action.value,
            "confidence": d.confidence,
            "reason": d.reason,
            "iteration": d.iteration,
            "metadata": d.metadata,
        }
