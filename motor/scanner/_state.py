"""ScannerState — estado compartido del subsistema de escaneo."""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScannerState:
    executor: object
    config: object


def build_scanner_state(config=None):
    from motor.core.config import UraConfig
    from motor.core.executor import SubprocessExecutor

    if config is None:
        config = UraConfig.load()

    return ScannerState(
        executor=SubprocessExecutor(),
        config=config,
    )
