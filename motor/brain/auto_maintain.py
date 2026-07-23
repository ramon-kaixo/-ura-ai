"""Automantenimiento nivel 1 del cerebro.

Flujo:
1. Detecta anomalia (Observer + AlertEngine)
2. Propone plan de accion
3. Espera aprobacion humana (Y/n)
4. Ejecuta via tuneladora
5. Verifica que se resolvio
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
import logging

from motor.brain.observer import BrainObserver
from motor.brain.alerts import AlertEngine, Alert
from motor.brain.executor import ProposalExecutor

log = logging.getLogger("ura.brain.auto_maintain")


@dataclass
class MaintenanceProposal:
    alert: Alert
    action: str
    target: str
    params: dict[str, Any]
    estimated_risk: str


class AutoMaintainer:
    """Propone fixes automaticos, espera aprobacion."""

    def __init__(self, observer: BrainObserver, executor: ProposalExecutor) -> None:
        self._observer = observer
        self._alerts = AlertEngine(observer)
        self._executor = executor
        self._pending: list[MaintenanceProposal] = []
        self._resolved: list[dict[str, Any]] = []

    def scan(self) -> list[MaintenanceProposal]:
        alerts = self._alerts.evaluate()
        proposals: list[MaintenanceProposal] = []
        for alert in alerts:
            prop = self._alert_to_proposal(alert)
            if prop:
                proposals.append(prop)
        self._pending.extend(proposals)
        return proposals

    @staticmethod
    def _alert_to_proposal(alert: Alert) -> MaintenanceProposal | None:
        if alert.severity == "emergency" and "DISCO" in alert.title:
            return MaintenanceProposal(alert=alert, action="clean_disk", target="disk", params={"min_free_gb": 50, "aggressive": True}, estimated_risk="low")
        if "Provider caido" in alert.title:
            provider = alert.affected_subsystems[0]
            return MaintenanceProposal(alert=alert, action="restart_provider", target=provider, params={"provider": provider, "timeout": 30}, estimated_risk="medium")
        return None

    def approve_and_execute(self, proposal: MaintenanceProposal, approved: bool = True) -> dict[str, Any]:
        if not approved:
            log.info("Propuesta rechazada: %s", proposal.action)
            return {"status": "rejected", "proposal": str(proposal)}

        log.info("Ejecutando: %s en %s", proposal.action, proposal.target)
        exec_proposal: dict[str, Any] = {
            "type": "refactor",
            "target": proposal.target,
            "priority": "high" if proposal.estimated_risk == "high" else "medium",
        }
        exec_proposal.update(proposal.params)
        result = self._executor.execute(exec_proposal)
        time.sleep(2)
        verification = self._verify_resolution(proposal)
        record: dict[str, Any] = {"proposal": str(proposal), "execution": result, "verification": verification, "timestamp": time.time()}
        self._resolved.append(record)
        return record

    def _verify_resolution(self, proposal: MaintenanceProposal) -> dict[str, Any]:
        new_obs = self._observer.observe_all()
        for obs in new_obs:
            if obs.subsystem in proposal.alert.affected_subsystems:
                if obs.status == "ok" and not obs.anomaly:
                    return {"resolved": True, "subsystem": obs.subsystem, "status": "ok"}
                return {"resolved": False, "subsystem": obs.subsystem, "status": obs.status, "anomaly": obs.anomaly}
        return {"resolved": False, "error": "Subsystem not found"}

    def get_pending(self) -> list[MaintenanceProposal]:
        return self._pending

    def get_resolved(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._resolved[-limit:]
