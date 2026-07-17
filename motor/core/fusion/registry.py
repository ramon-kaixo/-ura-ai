"""Registro de componentes del módulo Knowledge Fusion (F25).

Permite registrar y recuperar implementaciones concretas de cada
contrato sin acoplar el pipeline a implementaciones específicas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.fusion.base import (
        ChangeDetector,
        ConflictResolver,
        EntityResolver,
        FusionEngine,
        KnowledgeMerger,
        MemoryCandidateSelector,
        SourceScorer,
    )


class FusionRegistry:
    """Registro de componentes de fusión.

    Cada categoría admite múltiples implementaciones identificadas
    por nombre. La implementación "default" es la que se usa
    si no se especifica otra.
    """

    def __init__(self) -> None:
        self._engines: dict[str, FusionEngine] = {}
        self._conflict_resolvers: dict[str, ConflictResolver] = {}
        self._source_scorers: dict[str, SourceScorer] = {}
        self._mergers: dict[str, KnowledgeMerger] = {}
        self._change_detectors: dict[str, ChangeDetector] = {}
        self._selectors: dict[str, MemoryCandidateSelector] = {}
        self._entity_resolvers: dict[str, EntityResolver] = {}

    # engines
    def register_engine(self, name: str, engine: FusionEngine) -> None:
        self._engines[name] = engine

    def get_engine(self, name: str = "default") -> FusionEngine:
        if name not in self._engines:
            raise KeyError(f"FusionEngine '{name}' not registered")
        return self._engines[name]

    def list_engines(self) -> list[str]:
        return list(self._engines)

    # conflict resolvers
    def register_conflict_resolver(self, name: str, resolver: ConflictResolver) -> None:
        self._conflict_resolvers[name] = resolver

    def get_conflict_resolver(self, name: str = "default") -> ConflictResolver:
        if name not in self._conflict_resolvers:
            raise KeyError(f"ConflictResolver '{name}' not registered")
        return self._conflict_resolvers[name]

    def list_conflict_resolvers(self) -> list[str]:
        return list(self._conflict_resolvers)

    # source scorers
    def register_source_scorer(self, name: str, scorer: SourceScorer) -> None:
        self._source_scorers[name] = scorer

    def get_source_scorer(self, name: str = "default") -> SourceScorer:
        if name not in self._source_scorers:
            raise KeyError(f"SourceScorer '{name}' not registered")
        return self._source_scorers[name]

    def list_source_scorers(self) -> list[str]:
        return list(self._source_scorers)

    # mergers
    def register_merger(self, name: str, merger: KnowledgeMerger) -> None:
        self._mergers[name] = merger

    def get_merger(self, name: str = "default") -> KnowledgeMerger:
        if name not in self._mergers:
            raise KeyError(f"KnowledgeMerger '{name}' not registered")
        return self._mergers[name]

    def list_mergers(self) -> list[str]:
        return list(self._mergers)

    # change detectors
    def register_change_detector(self, name: str, detector: ChangeDetector) -> None:
        self._change_detectors[name] = detector

    def get_change_detector(self, name: str = "default") -> ChangeDetector:
        if name not in self._change_detectors:
            raise KeyError(f"ChangeDetector '{name}' not registered")
        return self._change_detectors[name]

    def list_change_detectors(self) -> list[str]:
        return list(self._change_detectors)

    # selectors
    def register_selector(self, name: str, selector: MemoryCandidateSelector) -> None:
        self._selectors[name] = selector

    def get_selector(self, name: str = "default") -> MemoryCandidateSelector:
        if name not in self._selectors:
            raise KeyError(f"MemoryCandidateSelector '{name}' not registered")
        return self._selectors[name]

    def list_selectors(self) -> list[str]:
        return list(self._selectors)

    # entity resolvers
    def register_entity_resolver(self, name: str, resolver: EntityResolver) -> None:
        self._entity_resolvers[name] = resolver

    def get_entity_resolver(self, name: str = "default") -> EntityResolver:
        if name not in self._entity_resolvers:
            raise KeyError(f"EntityResolver '{name}' not registered")
        return self._entity_resolvers[name]

    def list_entity_resolvers(self) -> list[str]:
        return list(self._entity_resolvers)
