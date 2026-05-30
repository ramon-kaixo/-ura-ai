"""Stub: WebSearch — búsqueda web para agentes URA."""

import logging

log = logging.getLogger(__name__)


class WebSearch:
    """Realiza búsquedas web. TODO: integrar con API de búsqueda."""

    def __init__(self, **kwargs):
        log.info("WebSearch inicializado (stub)")

    def search(self, query: str, max_results: int = 5) -> list:
        return []


web_search = WebSearch()
