"""Stub: ConfidenceEstimator — estimación de confianza en respuestas."""

import logging

log = logging.getLogger(__name__)


class ConfidenceEstimator:
    """Estima la confianza de una respuesta del modelo."""

    def __init__(self, threshold: float = 0.7, **kwargs):
        self.threshold = threshold
        log.info("ConfidenceEstimator inicializado (stub)")

    def estimate(self, response: str, context: str = "") -> float:
        return 0.8

    def is_confident(self, response: str, context: str = "") -> bool:
        return self.estimate(response, context) >= self.threshold
