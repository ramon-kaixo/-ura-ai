"""Stub: FederatedClient — cliente de aprendizaje federado."""

import logging

log = logging.getLogger(__name__)


class FederatedClient:
    """Cliente para aprendizaje federado entre nodos URA."""

    def __init__(self, server_url: str = None, **kwargs):
        self.server_url = server_url
        log.info("FederatedClient inicializado (stub)")

    def sync(self) -> bool:
        return True

    def contribute(self, data: dict) -> bool:
        return True
