"""Schema.org templates — generación de JSON-LD válido para Capa 11.

Templates para los tipos principales del Knowledge Graph:
  - SoftwareVersion
  - BugReport
  - Person
  - Organization
  - Dataset (DCAT)
  - KnowledgeAsset → JSON-LD genérico
"""

from __future__ import annotations

import json
from typing import Any


def software_version(
    name: str, version: str, release_date: str, description: str = "", bugs: list[dict] | None = None
) -> dict:
    """Schema.org SoftwareVersion template."""
    entity: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "SoftwareVersion",
        "name": name,
        "version": version,
        "releaseDate": release_date,
    }
    if description:
        entity["description"] = description
    if bugs:
        entity["subjectOf"] = [
            {
                "@type": "BugReport",
                "identifier": b.get("id", ""),
                "description": b.get("description", ""),
                "status": b.get("status", "UNKNOWN"),
            }
            for b in bugs
        ]
    return entity


def bug_report(
    identifier: str,
    description: str,
    status: str = "OPEN",
    severity: str = "medium",
    affected_versions: list[str] | None = None,
) -> dict:
    """Schema.org BugReport template."""
    entity: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "BugReport",
        "identifier": identifier,
        "description": description,
        "status": status,
    }
    if affected_versions:
        entity["affectedRelease"] = [{"@type": "SoftwareVersion", "name": v} for v in affected_versions]
    return entity


def person(name: str, email: str = "", url: str = "") -> dict:
    """Schema.org Person template."""
    p: dict[str, Any] = {"@context": "https://schema.org", "@type": "Person", "name": name}
    if email:
        p["email"] = email
    if url:
        p["url"] = url
    return p


def organization(name: str, url: str = "") -> dict:
    """Schema.org Organization template."""
    o: dict[str, Any] = {"@context": "https://schema.org", "@type": "Organization", "name": name}
    if url:
        o["url"] = url
    return o


def dcat_dataset(
    name: str,
    description: str = "",
    fmt: str = "text/markdown",
    access_url: str = "",
    creator: str = "",
    issued: str = "",
) -> dict:
    """DCAT Dataset template."""
    d: dict[str, Any] = {
        "@context": "https://www.w3.org/ns/dcat",
        "@type": "dcat:Dataset",
        "dcterms:title": name,
        "dcterms:description": description,
    }
    if access_url:
        d["dcat:distribution"] = {
            "@type": "dcat:Distribution",
            "dcat:format": fmt,
            "dcat:accessURL": access_url,
        }
    if creator:
        d["dcterms:creator"] = creator
    if issued:
        d["dcterms:issued"] = issued
    return d


def asset_to_jsonld(asset: Any) -> str:
    """Convierte un KnowledgeAsset a JSON-LD genérico.

    Usa schema.org/DigitalDocument como tipo base.
    Los tipos específicos se mapean via registry.py.
    """
    from knowledge.engine.ontology.registry import asset_type_to_schema

    schema_type = asset_type_to_schema(asset.asset_type)
    entity: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "@id": f"ura:asset:{asset.asset_id}",
        "name": asset.metadata.get("title", asset.asset_id),
        "description": asset.metadata.get("description", ""),
        "dateCreated": asset.created_at,
        "dateModified": asset.updated_at,
    }
    if asset.metadata.get("author"):
        entity["author"] = person(asset.metadata["author"])
    if asset.metadata.get("license"):
        entity["license"] = asset.metadata["license"]
    if asset.relationships:
        entity["mentions"] = [
            {"@id": f"ura:asset:{r.target_id}", "description": r.relation} for r in asset.relationships
        ]

    return json.dumps(entity, indent=2, ensure_ascii=False)
