"""Mapping — conversión entre KnowledgeAsset y formatos externos.

- KnowledgeAsset → Schema.org JSON-LD
- KnowledgeAsset → DCAT
- KnowledgeAsset → W3C Prov
- KnowledgeAsset → OpenLineage event
"""

from __future__ import annotations

from datetime import UTC, datetime

from knowledge.engine.ontology.internal import KnowledgeAsset


def to_schema_jsonld(asset: KnowledgeAsset) -> str:
    """KnowledgeAsset → Schema.org JSON-LD."""
    from knowledge.engine.ontology.schema_org import asset_to_jsonld

    return asset_to_jsonld(asset)


def to_dcat(asset: KnowledgeAsset) -> dict:
    """KnowledgeAsset → DCAT Dataset."""
    return {
        "@context": "https://www.w3.org/ns/dcat",
        "@type": "dcat:Dataset",
        "dcterms:title": asset.metadata.get("title", asset.asset_id),
        "dcterms:description": asset.metadata.get("description", ""),
        "dcterms:created": asset.created_at,
        "dcterms:modified": asset.updated_at,
    }


def to_prov(asset: KnowledgeAsset) -> dict:
    """KnowledgeAsset → W3C Prov Entity."""
    return {
        "@context": "https://www.w3.org/ns/prov",
        "@id": f"ura:asset:{asset.asset_id}",
        "@type": "prov:Entity",
        "prov:generatedAtTime": asset.created_at,
    }


def to_openlineage(asset: KnowledgeAsset, job_name: str = "metadata_extract", run_id: str = "") -> dict:
    """KnowledgeAsset → OpenLineage event (formato reducido).

    Para eventos completos, usar LineageStore con el schema completo OpenLineage.
    """
    return {
        "eventType": "COMPLETE",
        "eventTime": datetime.now(UTC).isoformat(),
        "run": {"runId": run_id or asset.asset_id},
        "job": {"namespace": "knowledge.engine", "name": job_name},
        "outputs": [
            {
                "namespace": "knowledge.engine",
                "name": f"asset:{asset.asset_id}",
                "facets": {
                    "schema": {
                        "_producer": "knowledge.engine.ontology",
                        "fields": [{"name": k, "type": type(v).__name__} for k, v in asset.metadata.items()],
                    }
                },
            }
        ],
    }
