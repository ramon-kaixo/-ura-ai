"""Internal models — KnowledgeAsset, AssetType, AssetSource, AssetRelationship.

KnowledgeAsset es el modelo base de la Capa 11. NO sustituye a Document ni SourceObject.
Los envuelve mediante metadata["wraps"] = "document:{doc_id}".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from knowledge.engine._compat import StrEnum


class AssetType(StrEnum):
    """Tipos de activos de conocimiento. Extensible."""
    MARKDOWN = "markdown"
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    PDF = "pdf"
    OFFICE_DOC = "office_doc"
    OFFICE_SHEET = "office_sheet"
    OFFICE_SLIDE = "office_slide"
    CONVERSATION = "conversation"
    GIT_REPO = "git_repo"
    API_REFERENCE = "api_reference"
    DECISION = "decision"
    INCIDENT = "incident"
    DATASET = "dataset"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AssetSource:
    """Origen de un KnowledgeAsset.

    kind: "filesystem" | "github" | "api" | "upload" | "compile" | "audit"
    location: path absoluto, URL, o identificador único.
    """
    kind: str
    location: str
    fetched_at: str = ""


@dataclass(frozen=True)
class AssetRelationship:
    """Relación dirigida entre dos KnowledgeAssets."""
    target_id: str
    relation: str  # "fixes" | "depends_on" | "references" | "generates" | …
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeAsset:
    """Activo de conocimiento con metadatos enriquecidos.

    NO reemplaza a Document ni SourceObject.
    Para enlazar con modelos existentes, usar metadata["wraps"]:
      - "document:{doc_id}"
      - "source:{path}"
      - "compile:{run_id}"
      - "audit:{audit_id}"
    """

    asset_id: str
    asset_type: AssetType
    metadata: dict[str, Any] = field(default_factory=dict)
    source: AssetSource = field(default_factory=lambda: AssetSource(kind="unknown", location=""))
    relationships: tuple[AssetRelationship, ...] = ()
    quality: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type.value,
            "metadata": self.metadata,
            "source": {"kind": self.source.kind, "location": self.source.location},
            "relationships": [
                {"target_id": r.target_id, "relation": r.relation, "metadata": r.metadata}
                for r in self.relationships
            ],
            "quality": self.quality,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeAsset:
        source_data = data.get("source", {})
        source = AssetSource(
            kind=source_data.get("kind", "unknown"),
            location=source_data.get("location", ""),
            fetched_at=source_data.get("fetched_at", ""),
        )
        rels = tuple(
            AssetRelationship(
                target_id=r["target_id"],
                relation=r.get("relation", "references"),
                metadata=r.get("metadata", {}),
            )
            for r in data.get("relationships", [])
        )
        return cls(
            asset_id=data["asset_id"],
            asset_type=AssetType(data.get("asset_type", "unknown")),
            metadata=data.get("metadata", {}),
            source=source,
            relationships=rels,
            quality=float(data.get("quality", 0.0)),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def to_jsonld(self) -> str:
        """Serializa a JSON-LD (Schema.org)."""
        from knowledge.engine.ontology.schema_org import asset_to_jsonld

        return asset_to_jsonld(self)

    def wraps_document(self, doc_id: str) -> None:
        """Marca este asset como envoltura de un Document existente."""
        # No se puede modificar frozen dataclass, devolvemos nuevo
        pass
