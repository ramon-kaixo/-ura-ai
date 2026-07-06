"""Ontology — modelos semánticos para Capa 11.

Paquete:
  internal.py    — KnowledgeAsset, AssetType, AssetSource, AssetRelationship
  schema_org.py  — Schema.org templates (SoftwareVersion, BugReport, Person, …)
  registry.py    — AssetType ↔ Schema.org type mapping
  mapping.py     — KnowledgeAsset → JSON-LD / DCAT / OpenLineage
"""

from knowledge.engine.ontology.internal import AssetRelationship as AssetRelationship
from knowledge.engine.ontology.internal import AssetSource as AssetSource
from knowledge.engine.ontology.internal import AssetType as AssetType
from knowledge.engine.ontology.internal import KnowledgeAsset as KnowledgeAsset
from knowledge.engine.ontology.mapping import to_dcat as to_dcat
from knowledge.engine.ontology.mapping import to_openlineage as to_openlineage
from knowledge.engine.ontology.mapping import to_prov as to_prov
from knowledge.engine.ontology.mapping import to_schema_jsonld as to_schema_jsonld
from knowledge.engine.ontology.registry import asset_type_to_schema as asset_type_to_schema
from knowledge.engine.ontology.registry import register_schema_mapping as register_schema_mapping
from knowledge.engine.ontology.schema_org import bug_report as bug_report
from knowledge.engine.ontology.schema_org import dcat_dataset as dcat_dataset
from knowledge.engine.ontology.schema_org import organization as organization
from knowledge.engine.ontology.schema_org import person as person
from knowledge.engine.ontology.schema_org import software_version as software_version
