"""Tests para knowledge/engine/ontology/schema_org.py — Fase 4 (B2)."""

from __future__ import annotations

import json
from typing import Any

from knowledge.engine.ontology import schema_org


class _FakeAsset:
    def __init__(self, *, asset_type: str = "bug_report", asset_id: str = "a1", metadata: dict | None = None) -> None:
        self.asset_type = asset_type
        self.asset_id = asset_id
        self.metadata = metadata or {}
        self.created_at = "2026-01-01"
        self.updated_at = "2026-01-02"
        self.relationships: list[Any] = []


class TestSoftwareVersion:
    def test_minimal(self) -> None:
        e = schema_org.software_version("URA", "1.0", "2026-01-01")
        assert e["@context"] == "https://schema.org"
        assert e["@type"] == "SoftwareVersion"
        assert e["version"] == "1.0"
        assert "description" not in e

    def test_with_description(self) -> None:
        e = schema_org.software_version("URA", "1.0", "2026-01-01", "desc")
        assert e["description"] == "desc"

    def test_with_bugs(self) -> None:
        e = schema_org.software_version("URA", "1.0", "2026-01-01", bugs=[{"id": "B1", "description": "d", "status": "OPEN"}])
        assert e["subjectOf"][0]["@type"] == "BugReport"
        assert e["subjectOf"][0]["identifier"] == "B1"
        assert e["subjectOf"][0]["status"] == "OPEN"

    def test_bug_defaults(self) -> None:
        e = schema_org.software_version("URA", "1.0", "2026-01-01", bugs=[{"id": "B2"}])
        assert e["subjectOf"][0]["status"] == "UNKNOWN"
        assert e["subjectOf"][0]["description"] == ""


class TestBugReport:
    def test_minimal(self) -> None:
        e = schema_org.bug_report("B1", "falla")
        assert e["@type"] == "BugReport"
        assert e["status"] == "OPEN"

    def test_custom_status_and_severity(self) -> None:
        e = schema_org.bug_report("B1", "falla", status="FIXED", severity="high")
        assert e["status"] == "FIXED"

    def test_affected_versions(self) -> None:
        e = schema_org.bug_report("B1", "falla", affected_versions=["1.0", "1.1"])
        assert e["affectedRelease"] == [
            {"@type": "SoftwareVersion", "name": "1.0"},
            {"@type": "SoftwareVersion", "name": "1.1"},
        ]

    def test_no_affected_versions(self) -> None:
        e = schema_org.bug_report("B1", "falla")
        assert "affectedRelease" not in e


class TestPersonOrg:
    def test_person_minimal(self) -> None:
        e = schema_org.person("Ana")
        assert e["@type"] == "Person"
        assert "email" not in e

    def test_person_full(self) -> None:
        e = schema_org.person("Ana", email="a@x.com", url="http://x.com")
        assert e["email"] == "a@x.com"
        assert e["url"] == "http://x.com"

    def test_organization(self) -> None:
        e = schema_org.organization("URA", "http://ura.io")
        assert e["@type"] == "Organization"
        assert e["url"] == "http://ura.io"


class TestDcat:
    def test_minimal(self) -> None:
        e = schema_org.dcat_dataset("dataset")
        assert e["@type"] == "dcat:Dataset"
        assert "dcat:distribution" not in e

    def test_full(self) -> None:
        e = schema_org.dcat_dataset(
            "dataset",
            description="d",
            fmt="application/json",
            access_url="http://data/x",
            creator="ura",
            issued="2026-01-01",
        )
        assert e["dcat:distribution"]["dcat:format"] == "application/json"
        assert e["dcterms:creator"] == "ura"
        assert e["dcterms:issued"] == "2026-01-01"


class TestAssetToJsonLd:
    def test_minimal(self) -> None:
        out = schema_org.asset_to_jsonld(_FakeAsset())
        e = json.loads(out)
        assert e["@type"] == "DigitalDocument"
        assert e["@id"] == "ura:asset:a1"
        assert e["name"] == "a1"

    def test_metadata_title_and_author(self) -> None:
        asset = _FakeAsset(metadata={"title": "Título", "author": "Ana", "license": "MIT"})
        e = json.loads(schema_org.asset_to_jsonld(asset))
        assert e["name"] == "Título"
        assert e["author"]["@type"] == "Person"
        assert e["license"] == "MIT"

    def test_relationships(self) -> None:
        rel = type("Rel", (), {"target_id": "a2", "relation": "references"})()
        asset = _FakeAsset(asset_id="a1")
        asset.relationships = [rel]
        e = json.loads(schema_org.asset_to_jsonld(asset))
        assert e["mentions"] == [{"@id": "ura:asset:a2", "description": "references"}]

    def test_unknown_type_falls_back(self) -> None:
        e = json.loads(schema_org.asset_to_jsonld(_FakeAsset(asset_type="cosa_rara")))
        assert e["@type"] == "DigitalDocument"
