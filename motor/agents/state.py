"""F27 — Máquina de estados explícita para AgentState.

Valida todas las transiciones. No permite cambios arbitrarios.
"""

from __future__ import annotations

from motor.agents.base import StateMachine as StateMachineABC
from motor.agents.models import AgentState


# Mapa de transiciones válidas: (desde, hacia) → permitido
_VALID_TRANSITIONS: set[tuple[AgentState, AgentState]] = {
    # CREATED → PLANIFICACIÓN
    (AgentState.CREATED, AgentState.PLANNING),
    (AgentState.CREATED, AgentState.CANCELLED),
    # PLANNING → READY o FAILED
    (AgentState.PLANNING, AgentState.READY),
    (AgentState.PLANNING, AgentState.FAILED),
    (AgentState.PLANNING, AgentState.CANCELLED),
    # READY → RUNNING o CANCELLED
    (AgentState.READY, AgentState.RUNNING),
    (AgentState.READY, AgentState.CANCELLED),
    # RUNNING → WAITING, COMPLETED, FAILED, CANCELLED, TIMEOUT
    (AgentState.RUNNING, AgentState.WAITING),
    (AgentState.RUNNING, AgentState.COMPLETED),
    (AgentState.RUNNING, AgentState.FAILED),
    (AgentState.RUNNING, AgentState.CANCELLED),
    (AgentState.RUNNING, AgentState.TIMEOUT),
    (AgentState.RUNNING, AgentState.PERMISSION_DENIED),
    (AgentState.RUNNING, AgentState.TOOL_ERROR),
    (AgentState.RUNNING, AgentState.LLM_ERROR),
    # WAITING → RUNNING, FAILED, CANCELLED, TIMEOUT
    (AgentState.WAITING, AgentState.RUNNING),
    (AgentState.WAITING, AgentState.FAILED),
    (AgentState.WAITING, AgentState.CANCELLED),
    (AgentState.WAITING, AgentState.TIMEOUT),
    # PERMISSION_DENIED → CANCELLED (terminal, pero puede cancelarse)
    (AgentState.PERMISSION_DENIED, AgentState.CANCELLED),
}


class AgentStateMachine(StateMachineABC):
    """Máquina de estados explícita para AgentState.

    Sin lógica de negocio. Solo validación de transiciones.
    """

    def transition(self, current: AgentState, target: AgentState) -> AgentState:
        if (current, target) not in _VALID_TRANSITIONS:
            raise ValueError(
                f"Invalid state transition: {current.value} → {target.value}"
            )
        return target

    def valid_transitions(self, state: AgentState) -> list[AgentState]:
        return [t for (s, t) in _VALID_TRANSITIONS if s == state]

    def is_terminal(self, state: AgentState) -> bool:
        return state in {
            AgentState.COMPLETED,
            AgentState.FAILED,
            AgentState.CANCELLED,
            AgentState.TIMEOUT,
            AgentState.PERMISSION_DENIED,
            AgentState.TOOL_ERROR,
            AgentState.LLM_ERROR,
        }
