"""Stub: SemanticBrain — memoria semántica para agentes URA."""

import logging

log = logging.getLogger(__name__)


class SemanticBrain:
    """Memoria semántica basada en embeddings. TODO: implementar con vector store."""

    def __init__(self, model: str = "nomic-embed-text", **kwargs):
        self.model = model
        self.memories = []
        log.info("SemanticBrain inicializado (stub)")

    def store(self, text: str, metadata: dict = None) -> None:
        self.memories.append({"text": text, "metadata": metadata or {}})

    def search(self, query: str, top_k: int = 5) -> list:
        return self.memories[:top_k]

    def clear(self) -> None:
        self.memories.clear()
