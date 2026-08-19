"""Tests de cobertura para knowledge/engine/ontology/schema_org.py."""

from __future__ import annotations

import json

from knowledge.engine.ontology.schema_org import (
    asset_to_jsonld,
    bug_report,
    dcat_dataset,
    organization,
    person,
    software_version,
)


def test_software_version_minimo() -> None:
    d = software_version("ura", "1.0", "2026-01-01")
    assert d["@type"] == "SoftwareVersion"
    assert "description" not in d
    assert "subjectOf" not in d


def test_software_version_completo() -> None:
    d = software_version(
        "ura", "1.0", "2026-01-01", description="d", bugs=[{"id": "B1", "description": "bug", "status": "OPEN"}]
    )
    assert d["description"] == "d"
    assert d["subjectOf"][0]["identifier"] == "B1"
    assert d["subjectOf"][0]["status"] == "OPEN"


def test_software_version_bug_sin_campos() -> None:
    d = software_version("ura", "1.0", "2026-01-01", bugs=[{}])
    assert d["subjectOf"][0]["identifier"] == ""
    assert d["subjectOf"][0]["status"] == "UNKNOWN"


def test_bug_report_minimo() -> None:
    d = bug_report("B1", "desc")
    assert d["status"] == "OPEN"
    assert "affectedRelease" not in d


def test_bug_report_con_versiones() -> None:
    d = bug_report("B1", "desc", status="CLOSED", affected_versions=["1.0", "1.1"])
    assert d["status"] == "CLOSED"
    assert d["affectedRelease"][0]["name"] == "1.0"


def test_person_minimo() -> None:
    d = person("Ana")
    assert d["@type"] == "Person"
    assert "email" not in d


def test_person_con_datos() -> None:
    d = person("Ana", email="a@x.com", url="https://x")
    assert d["email"] == "a@x.com"
    assert d["url"] == "https://x"


def test_organization_minimo() -> None:
    d = organization("Org")
    assert d["@type"] == "Organization"


def test_organization_con_url() -> None:
    d = organization("Org", url="https://o")
    assert d["url"] == "https://o"


def test_dcat_minimo() -> None:
    d = dcat_dataset("D")
    assert d["@type"] == "dcat:Dataset"
    assert "dcat:distribution" not in d


def test_dcat_completo() -> None:
    d = dcat_dataset("D", fmt="text/plain", access_url="https://a", creator="c", issued="2026")
    assert d["dcat:distribution"]["dcat:format"] == "text/plain"
    assert d["dcterms:creator"] == "c"
    assert d["dcterms:issued"] == "2026"


def test_asset_to_jsonld_minimo() -> None:
    from knowledge.engine.asset_store import AssetType

    class FakeAsset:
        asset_id = "a1"
        asset_type = AssetType.MARKDOWN
        metadata = {"title": "t"}
        created_at = "c"
        updated_at = "u"
        relationships = ()

    out = json.loads(asset_to_jsonld(FakeAsset()))
    assert out["@type"] == "DigitalDocument"
    assert out["name"] == "t"
    assert "author" not in out
    assert "mentions" not in out


def test_asset_to_jsonld_completo() -> None:
    from knowledge.engine.asset_store import AssetType

    class Rel:
        target_id = "b1"
        relation = "links"

    class FakeAsset:
        asset_id = "a1"
        asset_type = AssetType.VIDEO
        metadata = {"title": "t", "author": "Ana", "license": "MIT"}
        created_at = "c"
        updated_at = "u"
        relationships = (Rel(),)

    out = json.loads(asset_to_jsonld(FakeAsset()))
    assert out["author"]["name"] == "Ana"
    assert out["license"] == "MIT"
    assert out["mentions"][0]["@id"] == "ura:asset:b1"
