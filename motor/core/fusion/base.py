"""Contratos abstractos del módulo Knowledge Fusion (F25).

Define las interfaces para extraer, normalizar, resolver entidades,
detectar conflictos, puntuar fuentes, fusionar conocimiento y
detectar cambios.

Ninguna implementación concreta todavía — solo contratos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from motor.core.fusion.models import StageProvenance

if TYPE_CHECKING:
    from motor.core.fusion.engine import FusionStage
    from motor.core.fusion.models import (
        Conflict,
        EvidenceSet,
        FusionContext,
        FusionResult,
        KnowledgeClaim,
        KnowledgeDelta,
        KnowledgeFact,
        ResolvedEntity,
        SourceScore,
    )
    from motor.core.web.citation.citation import CitationBundle
    from motor.core.web.models import WebDocument


class FusionEngine(ABC):
    """Motor principal de fusión de conocimiento.

    Coordina el pipeline completo: extracción, normalización,
    resolución de entidades, detección de conflictos, scoring,
    merge y delta.
    """

    @abstractmethod
    def fuse(
        self,
        bundle: CitationBundle,
        documents: list[WebDocument],
    ) -> FusionResult:
        """Ejecuta el pipeline completo de fusión."""
        ...


class ConflictResolver(ABC):
    """Detecta y resuelve conflictos entre Claims."""

    @abstractmethod
    def detect(self, claims: list[KnowledgeClaim]) -> list[Conflict]:
        """Encuentra conflictos entre todos los pares de Claims."""
        ...

    @abstractmethod
    def resolve(
        self,
        conflicts: list[Conflict],
        claims: list[KnowledgeClaim],
    ) -> tuple[list[KnowledgeFact], list[Conflict]]:
        """Resuelve conflictos detectados.

        Retorna (facts_resueltos, conflictos_no_resueltos).
        """
        ...


class SourceScorer(ABC):
    """Evalúa la calidad y confianza de las fuentes."""

    @abstractmethod
    def score(self, claim: KnowledgeClaim) -> SourceScore:
        """Calcula la puntuación de una fuente para un Claim."""
        ...

    @abstractmethod
    def score_evidence(
        self,
        evidence_set: EvidenceSet,
    ) -> list[SourceScore]:
        """Calcula puntuaciones para todos los Claims de un conjunto."""
        ...


class EntityResolver(ABC):
    """Resuelve entidades a identificadores canónicos.

    Normaliza variaciones de una misma entidad:
    "Apple Inc." → "Apple" → "APPLE" → entity_id = E000123

    Retorna ResolvedEntity con entity_id, canonical_name, confidence,
    aliases, y versión del algoritmo.

    Si no puede resolver con suficiente confianza, debe retornar
    ResolvedEntity(status=ResolutionStatus.UNKNOWN) — abstención
    explícita en lugar de una resolución forzada.
    """

    @property
    @abstractmethod
    def version(self) -> str:
        """Versión del algoritmo de resolución (semver)."""
        ...

    @abstractmethod
    def resolve(
        self,
        text: str,
        context: dict | None = None,
    ) -> ResolvedEntity:
        """Retorna entidad resuelta con metadatos.

        Si no puede resolver: entity_id = "UNKNOWN_ENTITY".
        """
        ...

    @abstractmethod
    def resolve_many(
        self,
        texts: list[str],
        context: dict | None = None,
    ) -> list[ResolvedEntity]:
        """Resuelve múltiples textos a ResolvedEntity."""
        ...

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Normaliza un texto (lowercase, strip) sin resolver a ID."""
        ...


class PipelineStage(ABC):
    """Etapa individual del pipeline de fusión.

    Cada etapa recibe un FusionContext tipado y retorna el contexto
    actualizado. Esto permite insertar nuevas etapas sin modificar
    el orquestador (FusionPipeline).

    Cada etapa debe registrar su transformación en
    context.transforms para auditoría y depuración.
    """

    @property
    @abstractmethod
    def stage(self) -> FusionStage:
        """Tipo de etapa (FusionStage enum)."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre legible de la etapa (ej: 'EntityResolutionStage')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Versión semver de la implementación."""
        ...

    @property
    def deterministic(self) -> bool:
        """Si la etapa es determinista (misma entrada → misma salida).

        Etapas que usan LLM o aleatoriedad deben sobreescribir
        con False para señalizar que los benchmarks pueden variar.
        """
        return True

    @abstractmethod
    def execute(self, context: FusionContext) -> FusionContext:
        """Ejecuta la etapa y retorna el contexto actualizado.

        Implementaciones deben:
        1. Modificar context (claims, entities, conflicts, facts)
        2. Añadir StageProvenance a context.transforms
        3. Retornar el contexto modificado
        """
        ...


class BaseStage(PipelineStage):
    """PipelineStage con registro automático de StageProvenance.

    Las subclases implementan _execute() y obtienen automáticamente:
    - Registro de transformación en context.transforms
    - Conteo de claims input/output
    - Timestamp
    """

    def execute(self, context: FusionContext) -> FusionContext:
        input_claims = len(context.claims)
        input_facts = len(context.facts)
        result = self._execute(context)
        result.transforms.append(
            StageProvenance(
                stage_name=self.name,
                stage_version=self.version,
                transformer=f"{self.name}:v{self.version}",
                input_claims=input_claims,
                output_claims=len(result.claims),
            ),
        )
        if hasattr(self, "_record_stats"):
            result.statistics.setdefault("stages", {})[self.name] = {
                "version": self.version,
                "input_claims": input_claims,
                "output_claims": len(result.claims),
                "input_facts": input_facts,
                "output_facts": len(result.facts),
            }
        return result

    @abstractmethod
    def _execute(self, context: FusionContext) -> FusionContext: ...


class KnowledgeMerger(ABC):
    """Fusiona Claims en Facts consolidados.

    Estrategia intercambiable registrada en FusionRegistry.
    """

    @abstractmethod
    def merge(
        self,
        claims: list[KnowledgeClaim],
        conflicts: list[Conflict],
    ) -> list[KnowledgeFact]:
        """Agrupa Claims relacionados en Facts consolidados."""
        ...


class ChangeDetector(ABC):
    """Detecta cambios entre estados de conocimiento."""

    @abstractmethod
    def detect_delta(
        self,
        new_facts: list[KnowledgeFact],
        existing_facts: list[KnowledgeFact],
    ) -> KnowledgeDelta:
        """Compara dos conjuntos de Facts y retorna el delta."""
        ...


class MemoryCandidateSelector(ABC):
    """Selecciona Facts candidatos para almacenar en memoria persistente."""

    @abstractmethod
    def select(
        self,
        fusion_result: FusionResult,
        max_candidates: int = 100,
    ) -> list[KnowledgeFact]:
        """Selecciona los Facts más relevantes para memoria."""
        ...
