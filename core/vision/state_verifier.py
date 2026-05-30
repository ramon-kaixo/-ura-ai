"""Stub: StateVerifier — verificación visual de estado. TODO: implementar con llama3.2-vision."""

import logging

log = logging.getLogger(__name__)


class StateVerifier:
    """Verifica el estado visual de la interfaz o entorno."""

    def __init__(self, model: str = "llama3.2-vision:11b", **kwargs):
        self.model = model
        log.info("StateVerifier inicializado (stub)")

    def verify(self, image_path: str = None, expected_state: str = None) -> dict:
        return {"verified": True, "confidence": 0.0, "state": "stub"}

    def capture_and_verify(self, expected: str) -> bool:
        return True
