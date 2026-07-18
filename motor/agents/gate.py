"""CapabilityGate — perímetro de seguridad del sistema de agentes.

Toda operación de un agente sobre la plataforma pasa por aquí.
Sin excepción. Sin rutas alternativas.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from motor.agents.base import CapabilityGate as CapabilityGateABC
from motor.agents.models import AgentCapability, AuditEvent

if TYPE_CHECKING:
    from motor.agents.models import AgentExecution


# ── Códigos de denegación ─────────────────


class DenialCode(StrEnum):
    """Códigos explícitos de denegación de permiso.

    Cada código tiene un motivo concreto. Sin mensajes genéricos.
    """

    CAPABILITY_NOT_GRANTED = "capability_not_granted"
    CAPABILITY_NOT_RECOGNIZED = "capability_not_recognized"
    EXECUTION_NOT_FOUND = "execution_not_found"
    AGENT_CANCELLED = "agent_cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"
    GATE_CLOSED = "gate_closed"


# ── PermissionDecision ─────────────────────


@dataclass(frozen=True)
class PermissionDecision:
    """Resultado de una verificación de permiso.

    Contiene el motivo explícito de denegación o la confirmación.
    Toda decisión queda registrada en auditoría.
    """

    granted: bool
    capability: AgentCapability
    agent_id: str
    denial_code: DenialCode | None = None
    denial_reason: str = ""
    timestamp: float = 0.0
    cached: bool = False


# ── CapabilityGate concreto ────────────────


class AgentCapabilityGate(CapabilityGateABC):
    """Implementación concreta de CapabilityGate.

    Perímetro de seguridad único para todas las operaciones de agentes.
    Toda decisión es auditada. Sin excepciones.

    Complejidad: O(1) para verificación de permisos.
    Determinismo: misma capability + mismo estado → misma decisión.
    """

    def __init__(
        self,
        execution: AgentExecution,
        enable_cache: bool = False,
    ) -> None:
        self._execution = execution
        self._capabilities = execution.capabilities
        self._closed: bool = False
        self._decisions: list[PermissionDecision] = []
        self._lock = threading.Lock()
        self._enable_cache = enable_cache
        self._cache: dict[AgentCapability, PermissionDecision] = {}

    # ── API pública ──────────────────────────────────

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        """Cierra el gate. Todas las verificaciones posteriores deniegan."""
        self._closed = True

    @property
    def decisions(self) -> list[PermissionDecision]:
        """Todas las decisiones tomadas por este gate."""
        return list(self._decisions)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def granted_count(self) -> int:
        return sum(1 for d in self._decisions if d.granted)

    @property
    def denied_count(self) -> int:
        return sum(1 for d in self._decisions if not d.granted)

    # ── Implementación de CapabilityGate ──────────────

    def check(self, required: AgentCapability) -> None:
        """Verifica la capability. O(1). Lanza PermissionError si no concedida.

        Toda decisión (concedida o denegada) se registra en auditoría.
        """
        decision = self._decide(required)

        if not decision.granted:
            raise PermissionError(
                f"[{decision.denial_code.value}] "
                f"{decision.denial_reason} "
                f"(capability: {required.value}, agent: {decision.agent_id})"
            )

    def capabilities(self) -> set[AgentCapability]:
        return set(self._capabilities)

    # ── Interno: decisión ─────────────────────────────

    def _decide(self, capability: AgentCapability) -> PermissionDecision:
        """Evalúa y registra una decisión. O(1)."""

        # Cache hit: devolver decisión previa pero igual registrar
        if self._enable_cache and capability in self._cache:
            cached = self._cache[capability]
            decision = PermissionDecision(
                granted=cached.granted,
                capability=cached.capability,
                agent_id=cached.agent_id,
                denial_code=cached.denial_code,
                denial_reason=cached.denial_reason,
                timestamp=time.time(),
                cached=True,
            )
            with self._lock:
                self._decisions.append(decision)
            return decision

        decision = self._evaluate(capability)

        if self._enable_cache:
            self._cache[capability] = decision

        with self._lock:
            self._decisions.append(decision)

        return decision

    def _evaluate(self, capability: AgentCapability) -> PermissionDecision:
        """Evalúa la capability. Pura (sin efectos secundarios). Determinista."""
        agent_id = self._execution.agent_id
        ts = time.time()

        # Gate cerrado
        if self._closed:
            return PermissionDecision(
                granted=False, capability=capability, agent_id=agent_id,
                denial_code=DenialCode.GATE_CLOSED,
                denial_reason="CapabilityGate is closed",
                timestamp=ts,
            )

        # Capability no reconocida
        if not isinstance(capability, AgentCapability):
            return PermissionDecision(
                granted=False, capability=capability, agent_id=agent_id,
                denial_code=DenialCode.CAPABILITY_NOT_RECOGNIZED,
                denial_reason=f"Unknown capability: {capability}",
                timestamp=ts,
            )

        # Agente cancelado
        if self._execution.cancelled:
            return PermissionDecision(
                granted=False, capability=capability, agent_id=agent_id,
                denial_code=DenialCode.AGENT_CANCELLED,
                denial_reason="Agent was cancelled",
                timestamp=ts,
            )

        # Presupuesto excedido
        if self._execution.cost_units >= self._execution.policy.max_cost_units:
            return PermissionDecision(
                granted=False, capability=capability, agent_id=agent_id,
                denial_code=DenialCode.BUDGET_EXCEEDED,
                denial_reason=(
                    f"Budget exceeded: {self._execution.cost_units} >="
                    f" {self._execution.policy.max_cost_units}"
                ),
                timestamp=ts,
            )

        # Capability no concedida
        if capability not in self._capabilities:
            return PermissionDecision(
                granted=False, capability=capability, agent_id=agent_id,
                denial_code=DenialCode.CAPABILITY_NOT_GRANTED,
                denial_reason=f"Capability '{capability.value}' not in agent capabilities",
                timestamp=ts,
            )

        # Concedido
        return PermissionDecision(
            granted=True, capability=capability, agent_id=agent_id,
            timestamp=ts,
        )

    # ── Auditoría ─────────────────────────────────────

    def audit_events(self) -> list[AuditEvent]:
        """Genera eventos de auditoría para todas las decisiones."""
        events: list[AuditEvent] = []
        for d in self._decisions:
            events.append(AuditEvent(
                event_type="capability.check",
                agent_id=d.agent_id,
                timestamp=d.timestamp,
                data={
                    "capability": d.capability.value,
                    "granted": d.granted,
                    "denial_code": d.denial_code.value if d.denial_code else None,
                    "cached": d.cached,
                },
            ))
        return events
