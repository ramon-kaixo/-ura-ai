"""Puente entre KnowledgeFact (F25) y SemanticFact (memoria) — F25-A3.

Estrategia C: SemanticFact es una proyección/adaptador de KnowledgeFact.
El modelo canónico es KnowledgeFact. SemanticFact se deriva mediante
transformación explícita.

Contrato del bridge:
- Determinista: mismo KnowledgeFact → mismo dict
- Puro: sin efectos secundarios, sin IO, sin llamadas externas
- Idempotente: aplicar dos veces produce el mismo resultado
- Sin pérdida de información en los campos mapeados
- Datos perdidos documentados (no hay equivalente en SemanticFact)

NO hay transformación inversa (SemanticFact → KnowledgeFact).
El bridge es una proyección unidireccional.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.fusion.models import Fact, FactVersion, KnowledgeFact


# Datos que KnowledgeFact tiene y SemanticFact NO:
# - superseded_by: str | None  (gestión de versionado F25)
# - previous_version: str | None  (gestión de versionado F25)
# - evidence: tuple[Evidence, ...]  (campo deprecated)
# - source_score: SourceScore | None  (scoring de fuentes)
# Estos campos no tienen equivalente en el modelo de memoria episódica.


def knowledge_fact_to_semantic_fact(kf: KnowledgeFact) -> dict:
    """Proyecta un KnowledgeFact a un dict compatible con SemanticFact.

    Restricciones:
    - Sin pérdida en campos mapeados (ver docstring del módulo para pérdidas)
    - importance = confidence × 0.8 (heurística: confianza como importancia base)
    - source_episode_ids = evidence_ids (conversión semántica)
    """  # noqa: RUF002
    return {
        "id": kf.id,
        "subject": kf.subject,
        "predicate": kf.predicate,
        "object_value": kf.object,
        "confidence": kf.confidence,
        "importance": kf.confidence * 0.8,
        "source_episode_ids": list(kf.evidence_ids),
        "tags": ["fusion", "knowledge"],
        "version": kf.version,
        "created_at": kf.created_at or 0.0,
        "metadata": {
            "provenance": list(kf.provenance),
            "origin": "fusion_pipeline",
        },
    }


def fact_version_to_semantic_fact(fact: Fact, version: FactVersion) -> dict:
    """Proyecta un par (Fact, FactVersion) a dict compatible con SemanticFact.

    Restricciones:
    - Solo la versión vigente debe proyectarse (versiones obsoletas NO)
    - importance = confidence × 0.8
    """  # noqa: RUF002
    return {
        "id": fact.fact_id,
        "subject": fact.subject,
        "predicate": fact.predicate,
        "object_value": fact.object,
        "confidence": version.confidence,
        "importance": version.confidence * 0.8,
        "source_episode_ids": list(version.evidence_ids),
        "tags": ["fusion", "versioned"],
        "version": 1,
        "created_at": version.created_at,
        "metadata": {
            "provenance": list(version.provenance),
            "version_id": version.version_id,
            "supersedes": version.supersedes,
            "origin": "fusion_pipeline",
        },
    }
