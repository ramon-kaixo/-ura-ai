"""Automantenimiento nivel 1 + 2 del cerebro.

A1: Propone fixes, espera aprobacion humana, ejecuta, verifica.
A2: Autofix sin aprobacion para casos seguros (risk_level=safe).

Flujo A2:
1. Observer + AlertEngine detectan anomalia
2. AutoMaintainer clasifica riesgo (safe/medium/critical)
3. Si safe → ejecuta automaticamente
4. Si medium → pregunta humano (como A1)
5. Si critical → solo propone, no ejecuta
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
    risk_level: str = "medium"  # safe | medium | critical
    auto_execute: bool = False  # True = ejecutar sin preguntar


class AutoMaintainer:
    """Propone fixes, clasifica riesgo, ejecuta o pregunta segun nivel."""

    def __init__(self, observer: BrainObserver, executor: ProposalExecutor) -> None:
        self._observer = observer
        self._alerts = AlertEngine(observer)
        self._executor = executor
        self._pending: list[MaintenanceProposal] = []
        self._resolved: list[dict[str, Any]] = []

    # ── API publica ────────────────────────────────────────

    def scan(self) -> list[MaintenanceProposal]:
        """Escanea alertas y genera propuestas clasificadas por riesgo."""
        alerts = self._alerts.evaluate()
        proposals: list[MaintenanceProposal] = []

        for alert in alerts:
            prop = self._alert_to_proposal(alert)
            if prop is None:
                continue
            prop.risk_level = self._classify_risk(prop)
            if prop.risk_level == "safe":
                prop.auto_execute = True
            proposals.append(prop)

        self._pending.extend(proposals)
        return proposals

    def propose_and_maybe_execute(self) -> list[dict[str, Any]]:
        """A2: propone y ejecuta automaticamente los casos seguros.

        Retorna lista de resultados de ejecucion (automatica o pendiente).
        """
        results: list[dict[str, Any]] = []
        for proposal in self.scan():
            if proposal.auto_execute:
                log.info("A2 auto-execute: %s (risk=%s)", proposal.action, proposal.risk_level)
                result = self.approve_and_execute(proposal, approved=True)
                result["auto_executed"] = True
                results.append(result)
            else:
                log.info("A2 pending approval: %s (risk=%s)", proposal.action, proposal.risk_level)
                results.append({"status": "pending", "proposal": proposal, "auto_executed": False})
        return results

    def approve_and_execute(self, proposal: MaintenanceProposal, approved: bool = True) -> dict[str, Any]:
        """Ejecuta propuesta si esta aprobada o si es auto-executable.

        A2:
        - risk_level=safe y auto_execute=True → ejecuta sin preguntar
        - risk_level=medium → requiere approved=True (pregunta humana)
        - risk_level=critical → NO ejecuta aunque approved=True
        """
        if proposal.risk_level == "critical":
            log.warning("Propuesta CRITICAL no ejecutada: %s", proposal.action)
            return {
                "status": "critical_blocked",
                "reason": "risk_level=critical requiere intervencion manual",
                "proposal": proposal,
            }

        if not approved and not proposal.auto_execute:
            log.info("Propuesta rechazada: %s", proposal.action)
            return {"status": "rejected", "proposal": proposal}

        log.info("Ejecutando: %s en %s (risk=%s)", proposal.action, proposal.target, proposal.risk_level)

        exec_proposal: dict[str, Any] = {
            "type": self._action_to_type(proposal.action),
            "target": proposal.target,
            "priority": "high" if proposal.risk_level == "critical" else "medium",
            **proposal.params,
        }

        result = self._executor.execute(exec_proposal)

        time.sleep(2)
        verification = self._verify_resolution(proposal)

        record: dict[str, Any] = {
            "proposal": proposal,
            "execution": result,
            "verification": verification,
            "timestamp": time.time(),
        }
        self._resolved.append(record)
        return record

    # ── Clasificacion de riesgo (A2) ───────────────────────

    @staticmethod
    def _classify_risk(proposal: MaintenanceProposal) -> str:
        """Clasifica el riesgo de una propuesta.

        Retorna 'safe', 'medium' o 'critical'.
        Basado en el tipo de accion y severidad de la alerta.
        """
        action = proposal.action
        severity = proposal.alert.severity

        # Casos safe: autofix sin aprobacion (acciones cosmeticas o read-only)
        if action in ("auto_fix_ruff", "auto_fix_unused_imports"):
            return "safe"
        if action == "check_network":
            return "safe"
        if action == "clean_disk" and severity == "warning":
            return "safe"

        # Casos medium: requieren aprobacion humana
        if action in ("clean_disk", "restart_provider", "scale_resources"):
            return "medium"

        # Casos critical: no se ejecutan automaticamente
        if action == "emergency_shutdown":
            return "critical"

        return "medium"

    # ── Conversion alerta → propuesta ──────────────────────

    def _alert_to_proposal(self, alert: Alert) -> MaintenanceProposal | None:
        """Convierte una alerta en propuesta de accion."""
        if "DISCO" in alert.title.upper():
            return MaintenanceProposal(
                alert=alert,
                action="clean_disk",
                target="disk",
                params={"min_free_gb": 50, "aggressive": True},
            )
        if "caido" in alert.title.lower() or "caído" in alert.title.lower():
            provider = alert.affected_subsystems[0] if alert.affected_subsystems else "unknown"
            return MaintenanceProposal(
                alert=alert,
                action="restart_provider",
                target=provider,
                params={"provider": provider, "timeout": 30},
            )
        if "DEGRADACION" in alert.title or "DEGRADACIÓN" in alert.title:
            return MaintenanceProposal(
                alert=alert,
                action="scale_resources",
                target="system",
                params={"scale_type": "vertical", "urgent": True},
            )
        if "red" in alert.title.lower() or "network" in alert.title.lower():
            return MaintenanceProposal(
                alert=alert,
                action="check_network",
                target="network",
                params={"ping_targets": ["8.8.8.8", "1.1.1.1"]},
            )
        return None

    # ── Ejecucion y verificacion ───────────────────────────

    @staticmethod
    def _action_to_type(action: str) -> str:
        mapping: dict[str, str] = {
            "clean_disk": "refactor",
            "restart_provider": "refactor",
            "scale_resources": "refactor",
            "check_network": "test",
            "auto_fix_ruff": "format",
            "auto_fix_unused_imports": "format",
        }
        return mapping.get(action, "generic")

    def _verify_resolution(self, proposal: MaintenanceProposal) -> dict[str, Any]:
        """Verifica si la alerta se resolvio."""
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
