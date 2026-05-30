"""Stub: EpisodicMemory — memoria episódica para agentes URA."""

import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


class EpisodicMemory:
    """Almacena y recupera episodios de interacción. TODO: implementar persistencia."""

    def __init__(self, storage_path: str = None, **kwargs):
        self.episodes = []
        self.storage_path = Path(storage_path) if storage_path else None
        log.info("EpisodicMemory inicializado (stub)")

    def add_episode(self, event: str, context: dict = None) -> None:
        self.episodes.append(
            {
                "event": event,
                "context": context or {},
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_recent(self, n: int = 10) -> list:
        return self.episodes[-n:]

    def search(self, query: str, top_k: int = 5) -> list:
        return [e for e in self.episodes if query.lower() in e["event"].lower()][:top_k]
