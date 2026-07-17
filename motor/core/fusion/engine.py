"""Pipeline de fusión de conocimiento (F25).

Define las etapas del pipeline de fusión y el flujo de orquestación.
Sin implementación concreta — solo contratos y estructura.

El pipeline interno funciona como una lista de PipelineStage registradas,
lo que permite insertar nuevas etapas sin modificar el orquestador.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.fusion.base import (
        ChangeDetector,
        ConflictResolver,
        EntityResolver,
        FusionEngine,
        KnowledgeMerger,
        MemoryCandidateSelector,
        PipelineStage,
        SourceScorer,
    )
    from motor.core.fusion.models import FusionContext, FusionResult
    from motor.core.web.citation.citation import CitationBundle
    from motor.core.web.models import WebDocument


class FusionStage(StrEnum):
    """Etapas del pipeline de fusión."""

    EXTRACTION = "extraction"
    NORMALIZATION = "normalization"
    ENTITY_RESOLUTION = "entity_resolution"
    CONFLICT_DETECTION = "conflict_detection"
    SOURCE_SCORING = "source_scoring"
    MERGE = "merge"
    DELTA = "delta"
    SELECTION = "selection"


class FusionPipeline:
    """Orquestación del pipeline de fusión de conocimiento.

    Coordina las etapas: extracción → normalización → resolución
    de entidades → detección de conflictos → scoring → merge →
    delta → selección.

    Acepta componentes individuales (backward compatible) o una
    lista de PipelineStage. En F27 se podrán insertar etapas nuevas
    via register_stage() sin modificar este código.
    """

    def __init__(
        self,
        engine: FusionEngine | None = None,
        conflict_resolver: ConflictResolver | None = None,
        source_scorer: SourceScorer | None = None,
        merger: KnowledgeMerger | None = None,
        change_detector: ChangeDetector | None = None,
        selector: MemoryCandidateSelector | None = None,
        entity_resolver: EntityResolver | None = None,
        stages: list[PipelineStage] | None = None,
    ) -> None:
        self._stages: list[PipelineStage] = []
        self._stage_times: dict[FusionStage, float] = {}

        self._engine = engine
        if stages is not None:
            self._stages = list(stages)

    @property
    def engine(self) -> FusionEngine | None:
        return getattr(self, "_engine", None)

    @property
    def stages(self) -> list[PipelineStage]:
        return list(self._stages)

    @property
    def stage_times(self) -> dict[FusionStage, float]:
        return dict(self._stage_times)

    def register_stage(
        self,
        stage: PipelineStage,
        index: int | None = None,
    ) -> None:
        """Registra una etapa en el pipeline.

        Si index es None, se añade al final.
        Si index es un entero, se inserta en esa posición.
        """
        if index is None:
            self._stages.append(stage)
        else:
            self._stages.insert(index, stage)

    def run(
        self,
        bundle: CitationBundle,
        documents: list[WebDocument],
    ) -> FusionResult:
        """Ejecuta el pipeline completo de fusión.

        Si se proporcionaron componentes individuales, delega en
        FusionEngine.fuse(). Si se proporcionaron etapas, las
        ejecuta secuencialmente usando FusionContext.

        El resultado incluye un FactIndex con los Facts producidos,
        indexados por entidad, predicado y evidencia.
        """
        if self._engine is not None:
            return self._engine.fuse(bundle, documents)

        context = _build_context(bundle, documents)
        for stage in self._stages:
            context = stage.execute(context)
        result = _context_to_result(context)

        # Construir FactIndex desde los Facts producidos
        from motor.core.fusion.fact_index import FactIndex
        from motor.core.fusion.models import Fact, FactVersion, make_fact_id

        idx = FactIndex()
        for kf in result.accepted:
            fid = make_fact_id(kf.subject, kf.predicate, kf.object)
            fact = Fact(fact_id=fid, subject=kf.subject, predicate=kf.predicate, object=kf.object)
            version = FactVersion(
                version_id=f"v{kf.version}",
                fact_id=fid,
                confidence=kf.confidence,
                evidence_ids=kf.evidence_ids,
                provenance=kf.provenance,
                created_at=kf.created_at or 0.0,
            )
            idx.add_fact_version(fact, version)
        idx.freeze()
        result.index = idx

        return result


def _build_context(
    bundle: CitationBundle,
    documents: list[WebDocument],
) -> FusionContext:
    from motor.core.fusion.models import FusionContext

    return FusionContext(bundle=bundle, documents=documents)


def _context_to_result(context: FusionContext) -> FusionResult:
    from motor.core.fusion.models import FusionResult

    return FusionResult(
        accepted=tuple(context.facts),
        rejected=tuple(context.claims),
        conflicts=tuple(context.conflicts),
        warnings=tuple(context.warnings),
        statistics=dict(context.statistics),
        provenance=context.provenance,
    )
