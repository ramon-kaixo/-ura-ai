import logging

logger = logging.getLogger(__name__)


class Governance:
    def __init__(self, risk_threshold: float = 0.7) -> None:
        self.risk_threshold = risk_threshold
        self._risky_keywords = [
            "borrar",
            "eliminar",
            "pagar",
            "transferir",
            "enviar a externo",
            "despedir",
            "format",
            "rm -rf",
            "drop table",
            "shutdown",
            "reboot",
        ]

    def assess_risk(self, action_description: str) -> float:
        desc_lower = action_description.lower()
        matches = sum(1 for kw in self._risky_keywords if kw in desc_lower)
        if matches >= 2:
            return 1.0
        if matches == 1:
            return 0.8
        return 0.0

    def should_ask_human(self, action_desc: str) -> bool:
        risk = self.assess_risk(action_desc)
        if risk > self.risk_threshold:
            logger.warning("Accion de riesgo alto (%.2f): %s", risk, action_desc)
            return True
        return False

    def classify_action(self, action_desc: str) -> str:
        risk = self.assess_risk(action_desc)
        if risk > 0.7:
            return "critical"
        if risk > 0.3:
            return "moderate"
        return "safe"
