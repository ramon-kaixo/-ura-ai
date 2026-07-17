"""Puente entre KnowledgeFact (F25) y SemanticFact (memoria) — F25-A3.

Estrategia C: SemanticFact es una proyección/adaptador de KnowledgeFact.
El modelo canónico es KnowledgeFact. SemanticFact se deriva mediante
transformación explícita.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.fusion.models import Fact, FactVersion, KnowledgeFact


def knowledge_fact_to_semantic_fact(kf: KnowledgeFact) -> dict:
    """Proyecta un KnowledgeFact a un dict compatible con SemanticFact.

    No se importa SemanticFact directamente para evitar dependencias
    cruzadas en tiempo de importación. El dict resultante puede pasarse
    a SemanticMemoryStore.store() o a un constructor de SemanticFact.

    Mapeo:
    - subject → subject
    - predicate → predicate
    - object → object_value
    - confidence → confidence
    - evidence_ids → source_episode_ids (conversión semántica)
    - created_at → created_at
    - id → id
    - version → version
    """
    return {
        "id": kf.id,
        "subject": kf.subject,
        "predicate": kf.predicate,
        "object_value": kf.object,
        "confidence": kf.confidence,
        "importance": kf.confidence * 0.8,  # heurística: confianza como importancia base
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
    """Proyecta un par (Fact, FactVersion) a dict compatible con SemanticFact."""
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
