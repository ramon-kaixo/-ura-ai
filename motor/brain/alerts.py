"""Alertas inteligentes del cerebro.

Correlaciona observaciones de BrainObserver para evitar falsos positivos.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from motor.brain.observer import BrainObserver

log = __import__("logging").getLogger("ura.brain.alerts")


@dataclass
class Alert:
    severity: str
    title: str
    description: str
    affected_subsystems: list[str]
    timestamp: float
    suggested_action: str | None = None


class AlertEngine:
    """Genera alertas inteligentes correlacionando observaciones."""

    def __init__(self, observer: BrainObserver) -> None:
        self._observer = observer
        self._alert_history: list[Alert] = []

    def evaluate(self) -> list[Alert]:
        observations = self._observer.observe_all()
        alerts: list[Alert] = []

        # Patron 1: Provider caido
        for obs in observations:
            if obs.status == "error":
                alerts.append(
                    Alert(
                        severity="critical",
                        title=f"Provider caido: {obs.subsystem}",
                        description=f"{obs.subsystem}: {obs.anomaly or 'status unknown'}",
                        affected_subsystems=[obs.subsystem],
                        timestamp=time.time(),
                        suggested_action="Verificar conectividad y credenciales",
                    )
                )

        # Patron 2: Disco critico
        for obs in observations:
            if obs.subsystem == "disk":
                libre = obs.raw_data.get("libre_gb", 999)
                if libre < 10:
                    alerts.append(
                        Alert(
                            severity="emergency",
                            title="DISCO CRITICO",
                            description=f"Solo {libre:.1f}GB libres",
                            affected_subsystems=["disk"],
                            timestamp=time.time(),
                            suggested_action="Liberar espacio inmediatamente",
                        )
                    )
                elif libre < 50:
                    alerts.append(
                        Alert(
                            severity="warning",
                            title="Disco bajo",
                            description=f"{libre:.1f}GB libres",
                            affected_subsystems=["disk"],
                            timestamp=time.time(),
                            suggested_action="Ejecutar limpieza de logs",
                        )
                    )

        # Patron 3: Degradacion multiple (latencia + errores)
        latency_high = [o for o in observations if o.raw_data.get("latency_ms", 0) > 500]
        errors = [o for o in observations if o.status == "error"]
        if len(latency_high) >= 2 and len(errors) >= 1:
            subs = list(set([o.subsystem for o in latency_high + errors]))
            alerts.append(
                Alert(
                    severity="critical",
                    title="DEGRADACION DE SERVICIO",
                    description=f"Multiples subsistemas afectados: {subs}",
                    affected_subsystems=subs,
                    timestamp=time.time(),
                    suggested_action="Escalar recursos o investigar cuello de botella",
                )
            )

        # Patron 4: Latencia alta sin errores = posible red
        for obs in latency_high:
            if obs.status != "error" and obs.subsystem != "disk":
                alerts.append(
                    Alert(
                        severity="warning",
                        title=f"Posible problema de red: {obs.subsystem}",
                        description=f"Latencia {obs.raw_data.get('latency_ms', 0):.0f}ms",
                        affected_subsystems=[obs.subsystem],
                        timestamp=time.time(),
                        suggested_action="Verificar conectividad de red",
                    )
                )

        self._alert_history.extend(alerts)
        self._alert_history = self._alert_history[-100:]
        return alerts

    def get_history(self, limit: int = 20) -> list[Alert]:
        return self._alert_history[-limit:]

    def get_critical(self) -> list[Alert]:
        return [a for a in self._alert_history if a.severity in ("critical", "emergency")]
