"""Configuración del módulo Knowledge Fusion (F25)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass
class FusionConfig:
    """Configuración del pipeline de fusión de conocimiento."""

    enabled: bool = True
    default_engine: str = "default"
    default_conflict_resolver: str = "default"
    default_source_scorer: str = "default"
    default_merger: str = "default"
    default_change_detector: str = "default"
    default_selector: str = "default"
    max_claims_per_document: int = 50
    max_facts_per_run: int = 200
    min_confidence_threshold: float = 0.3
    max_unresolved_conflicts: int = 50
    stage_timing_enabled: bool = True

    # weights para scoring de fuentes
    authority_weight: float = 0.4
    freshness_weight: float = 0.3
    relevance_weight: float = 0.3

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def make_config_hash(config: FusionConfig) -> str:
    """Hash reproducible de la configuración.

    Usa JSON ordenado + UTF-8 + SHA-256 para garantizar que
    la misma configuración produzca siempre el mismo hash.
    """
    raw = json.dumps(config.to_dict(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
