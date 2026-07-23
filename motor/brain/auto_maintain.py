"""Automantenimiento nivel 1 del cerebro.

Flujo:
1. Detecta anomalía (Observer + AlertEngine)
2. Propone plan de acción
3. Espera aprobación humana (Y/n)
4. Ejecuta vía tuneladora
5. Verifica que se resolvió
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .alerts import Alert, AlertEngine

if TYPE_CHECKING:
    from .executor import ProposalExecutor
    from .observer import BrainObserver

log = logging.getLogger("ura.brain.auto_maintain")


@dataclass
class MaintenanceProposal:
    alert: Alert
    action: str
    target: str
    params: dict[str, Any]
    estimated_risk: str  # low, medium, high


class AutoMaintainer:
    """Propone fixes automáticos, espera aprobación."""

    def __init__(self, observer: BrainObserver, executor: ProposalExecutor) -> None:
        self._observer = observer
        self._alerts = AlertEngine(observer)
        self._executor = executor
        self._pending: list[MaintenanceProposal] = []
        self._resolved: list[dict[str, Any]] = []

    def scan(self) -> list[MaintenanceProposal]:
        """Escanea alertas y genera propuestas de mantenimiento."""
        alerts = self._alerts.evaluate()
        proposals = []

        for alert in alerts:
            prop = self._alert_to_proposal(alert)
            if prop:
                proposals.append(prop)

        self._pending.extend(proposals)
        return proposals

    def _alert_to_proposal(self, alert: Alert) -> MaintenanceProposal | None:
        """Convierte una alerta en propuesta de acción."""
        if alert.severity == "emergency" and "DISCO" in alert.title:
            return MaintenanceProposal(
                alert=alert,
                action="clean_disk",
                target="disk",
                params={"min_free_gb": 50, "aggressive": True},
                estimated_risk="low",
            )
        elif "Provider caído" in alert.title:
            provider = alert.affected_subsystems[0]
            return MaintenanceProposal(
                alert=alert,
                action="restart_provider",
                target=provider,
                params={"provider": provider, "timeout": 30},
                estimated_risk="medium",
            )
        elif "DEGRADACIÓN" in alert.title:
            return MaintenanceProposal(
                alert=alert,
                action="scale_resources",
                target="system",
                params={"scale_type": "vertical", "urgent": True},
                estimated_risk="high",
            )
        elif "RED" in alert.title:
            return MaintenanceProposal(
                alert=alert,
                action="check_network",
                target="network",
                params={"ping_targets": ["8.8.8.8", "1.1.1.1"]},
                estimated_risk="low",
            )
        return None

    def approve_and_execute(self, proposal: MaintenanceProposal, approved: bool = True) -> dict[str, Any]:
        """Ejecuta propuesta si está aprobada."""
        if not approved:
            log.info("Propuesta rechazada: %s", proposal.action)
            return {"status": "rejected", "proposal": proposal}

        log.info("Ejecutando: %s en %s", proposal.action, proposal.target)

        exec_proposal = {
            "type": self._action_to_type(proposal.action),
            "target": proposal.target,
            "priority": "high" if proposal.estimated_risk == "high" else "medium",
            **proposal.params,
        }

        result = self._executor.execute(exec_proposal)

        time.sleep(2)
        verification = self._verify_resolution(proposal)

        record = {
            "proposal": proposal,
            "execution": result,
            "verification": verification,
            "timestamp": time.time(),
        }
        self._resolved.append(record)
        return record

    def _action_to_type(self, action: str) -> str:
        mapping = {
            "clean_disk": "refactor",
            "restart_provider": "refactor",
            "scale_resources": "refactor",
            "check_network": "test",
        }
        return mapping.get(action, "generic")

    def _verify_resolution(self, proposal: MaintenanceProposal) -> dict[str, Any]:
        """Verifica si la alerta se resolvió."""
        new_obs = self._observer.observe_all()
        for obs in new_obs:
            if obs.subsystem in proposal.alert.affected_subsystems:
                if obs.status == "ok" and not obs.anomaly:
                    return {"resolved": True, "subsystem": obs.subsystem, "status": "ok"}
                else:
                    return {"resolved": False, "subsystem": obs.subsystem, "status": obs.status, "anomaly": obs.anomaly}
        return {"resolved": False, "error": "Subsystem not found in new observations"}

    def get_pending(self) -> list[MaintenanceProposal]:
        return self._pending

    def get_resolved(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._resolved[-limit:]
