"""Stub: LatentReward — sistema de recompensa latente para aprendizaje."""

import logging

log = logging.getLogger(__name__)


class LatentReward:
    """Calcula recompensas latentes para mejorar respuestas."""

    def __init__(self, **kwargs):
        self.history = []
        log.info("LatentReward inicializado (stub)")

    def compute_reward(self, action: str, outcome: str) -> float:
        return 0.5

    def update(self, action: str, reward: float) -> None:
        self.history.append({"action": action, "reward": reward})
