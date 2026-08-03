"""Tests para knowledge/engine/ontology/mapping.py y audit/backend.py."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from knowledge.engine.audit.backend import AuditBackend, AuditHealth, record_metric
from knowledge.engine.ontology.mapping import to_dcat, to_openlineage, to_prov, to_schema_jsonld


class FakeAsset:
    def __init__(self, asset_id="a1", metadata=None, created_at="2026-01-01", updated_at="2026-01-02"):
        self.asset_id = asset_id
        self.metadata = metadata if metadata is not None else {"title": "Titulo", "description": "Desc", "tags": ["x"]}
        self.created_at = created_at
        self.updated_at = updated_at


class TestMapping:
    def test_to_schema_jsonld(self, monkeypatch) -> None:
        asset = FakeAsset()
        monkeypatch.setattr("knowledge.engine.ontology.schema_org.asset_to_jsonld", mock.Mock(return_value='{"@type": "Thing"}'))
        out = to_schema_jsonld(asset)
        assert "Thing" in out

    def test_to_dcat(self) -> None:
        asset = FakeAsset()
        out = to_dcat(asset)
        assert out["@type"] == "dcat:Dataset"
        assert out["dcterms:title"] == "Titulo"
        assert out["dcterms:created"] == "2026-01-01"

    def test_to_dcat_sin_titulo(self) -> None:
        asset = FakeAsset(metadata={})
        out = to_dcat(asset)
        assert out["dcterms:title"] == "a1"  # fallback a asset_id

    def test_to_prov(self) -> None:
        asset = FakeAsset()
        out = to_prov(asset)
        assert out["@type"] == "prov:Entity"
        assert out["@id"] == "ura:asset:a1"

    def test_to_openlineage(self) -> None:
        asset = FakeAsset()
        out = to_openlineage(asset, job_name="mi_job", run_id="run1")
        assert out["eventType"] == "COMPLETE"
        assert out["run"]["runId"] == "run1"
        assert out["job"]["name"] == "mi_job"
        assert out["outputs"][0]["name"] == "asset:a1"

    def test_to_openlineage_sin_run_id(self) -> None:
        asset = FakeAsset(asset_id="abc")
        out = to_openlineage(asset)
        assert out["run"]["runId"] == "abc"  # fallback a asset_id

    def test_to_openlineage_metadata_types(self) -> None:
        asset = FakeAsset(metadata={"tags": ["x", "y"], "count": 3, "flag": True})
        out = to_openlineage(asset)
        fields = out["outputs"][0]["facets"]["schema"]["fields"]
        tipos = {f["name"]: f["type"] for f in fields}
        assert tipos["tags"] == "list"
        assert tipos["count"] == "int"
        assert tipos["flag"] == "bool"


class TestAuditBackend:
    def test_audit_health_defaults(self) -> None:
        h = AuditHealth()
        assert h.healthy is True
        assert h.error == ""
        assert h.events_written == 0

    def test_audit_health_con_valores(self) -> None:
        h = AuditHealth(healthy=False, error="boom", events_written=3)
        assert h.healthy is False
        assert h.error == "boom"
        assert h.events_written == 3

    def test_protocol_contrato(self) -> None:
        """AuditBackend es Protocol sin runtime_checkable — no permite isinstance."""
        assert callable(AuditBackend.write)
        assert callable(AuditBackend.flush)
        assert callable(AuditBackend.health_check)

    def test_record_metric(self, monkeypatch) -> None:
        metrics = mock.Mock()
        metrics.audit_write_failures = mock.Mock()
        metrics.audit_write_failures.inc = mock.Mock()
        monkeypatch.setattr("knowledge.engine.metrics.audit_write_failures", metrics.audit_write_failures)
        record_metric()
        metrics.audit_write_failures.inc.assert_called_once()

    def test_record_metric_sin_metrics(self, monkeypatch) -> None:
        monkeypatch.setattr("knowledge.engine.metrics.audit_write_failures", mock.Mock(side_effect=AttributeError("no")))
        record_metric()  # no debe lanzar
