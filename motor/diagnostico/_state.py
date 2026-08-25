"""DiagnosticoState — estado compartido del subsistema de diagnóstico."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.config import UraConfig

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiagnosticoState:
    executor: object
    config: object


def build_diagnostico_state(config: UraConfig | None = None) -> DiagnosticoState:
    from motor.core.config import UraConfig
    from motor.core.executor import SubprocessExecutor

    if config is None:
        config = UraConfig.load()

    return DiagnosticoState(
        executor=SubprocessExecutor(),
        config=config,
    )
