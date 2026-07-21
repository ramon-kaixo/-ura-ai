"""DiagnosticoState — estado compartido del subsistema de diagnóstico."""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiagnosticoState:
    executor: object
    config: object


def build_diagnostico_state(config=None):
    from motor.core.config import UraConfig
    from motor.core.executor import SubprocessExecutor

    if config is None:
        config = UraConfig.load()

    return DiagnosticoState(
        executor=SubprocessExecutor(),
        config=config,
    )
