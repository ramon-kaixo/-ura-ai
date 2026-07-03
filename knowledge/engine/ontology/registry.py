"""Registry — mapeo entre AssetType y Schema.org types.

Permite extender los tipos soportados sin modificar el código existente.
"""

from __future__ import annotations

from knowledge.engine.ontology.internal import AssetType

# Mapeo por defecto: AssetType → Schema.org type
_ASSET_TYPE_TO_SCHEMA: dict[AssetType, str] = {
    AssetType.MARKDOWN: "DigitalDocument",
    AssetType.VIDEO: "VideoObject",
    AssetType.IMAGE: "ImageObject",
    AssetType.AUDIO: "AudioObject",
    AssetType.PDF: "DigitalDocument",
    AssetType.OFFICE_DOC: "DigitalDocument",
    AssetType.OFFICE_SHEET: "Dataset",
    AssetType.OFFICE_SLIDE: "PresentationDigitalDocument",
    AssetType.CONVERSATION: "Conversation",
    AssetType.GIT_REPO: "SoftwareSourceCode",
    AssetType.API_REFERENCE: "TechArticle",
    AssetType.DECISION: "Decision",
    AssetType.INCIDENT: "Incident",
    AssetType.DATASET: "Dataset",
    AssetType.ARCHIVE: "Archive",
    AssetType.UNKNOWN: "DigitalDocument",
}


def asset_type_to_schema(asset_type: AssetType) -> str:
    """Retorna el Schema.org type para un AssetType."""
    return _ASSET_TYPE_TO_SCHEMA.get(asset_type, "DigitalDocument")


def register_schema_mapping(asset_type: AssetType, schema_type: str) -> None:
    """Registra un mapeo personalizado (extensión)."""
    _ASSET_TYPE_TO_SCHEMA[asset_type] = schema_type
