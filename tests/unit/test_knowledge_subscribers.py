"""Tests para knowledge/engine/subscribers.py — handlers del Event Bus."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

import knowledge.engine.subscribers as subs


class FakeEvent:
    def __init__(self, correlation_id="cid123", errors=0, documents_changed=2, documents_total=10, reason="cli"):
        self.correlation_id = correlation_id
        self.errors = errors
        self.documents_changed = documents_changed
        self.documents_total = documents_total
        self.reason = reason


class FakeBus:
    def __init__(self):
        self.subscribed = []

    def subscribe(self, event_type, handler):
        self.subscribed.append((event_type, handler))


@pytest.fixture(autouse=True)
def reset_subscribed(monkeypatch):
    monkeypatch.setattr(subs, "_SUBSCRIBED", False)
    yield
    monkeypatch.setattr(subs, "_SUBSCRIBED", False)


class TestSubscribeAll:
    def test_registra_handlers(self, tmp_path) -> None:
        bus = FakeBus()
        subs.subscribe_all(bus, tmp_path / "db.sqlite", tmp_path / "src")
        tipos = [t.__name__ for t, _ in bus.subscribed]
        assert tipos.count("CompileCompleted") == 5
        assert "SearchPerformed" in tipos
        assert "ArchiveCompleted" in tipos

    def test_idempotente(self, tmp_path) -> None:
        bus = FakeBus()
        subs.subscribe_all(bus, tmp_path / "db.sqlite", tmp_path / "src")
        subs.subscribe_all(bus, tmp_path / "db.sqlite", tmp_path / "src")
        assert len(bus.subscribed) == 7  # solo primera vez

    def test_con_vector(self, tmp_path) -> None:
        bus = FakeBus()
        embedder = mock.Mock()
        store = mock.Mock()
        subs.subscribe_all(bus, tmp_path / "db.sqlite", tmp_path / "src", embedder, store)
        tipos = [t.__name__ for t, _ in bus.subscribed]
        assert "MetadataExtracted" in tipos


class TestCompileArchiveHandler:
    def test_ok(self, tmp_path) -> None:
        handler = subs._make_compile_archive_handler(tmp_path / "db.sqlite", tmp_path / "src")
        enqueue = mock.Mock()
        process = mock.Mock()
        with mock.patch("knowledge.engine.jobs.enqueue_archive_job", enqueue):
            with mock.patch("knowledge.engine.jobs.process_archive_jobs", process):
                handler(FakeEvent())
        enqueue.assert_called_once()
        process.assert_called_once()

    def test_error(self, tmp_path) -> None:
        handler = subs._make_compile_archive_handler(tmp_path / "db.sqlite", tmp_path / "src")
        with mock.patch("knowledge.engine.jobs.enqueue_archive_job", mock.Mock(side_effect=OSError("boom"))):
            handler(FakeEvent())  # no debe lanzar


class TestCompileAuditHandler:
    def test_success(self) -> None:
        handler = subs._make_compile_audit_handler()
        audit = mock.Mock()
        with mock.patch("knowledge.engine.audit.get_audit", return_value=audit):
            handler(FakeEvent(errors=0))
        audit.log_compile.assert_called_once()
        assert audit.log_compile.call_args.kwargs["result"] == "success"

    def test_failure(self) -> None:
        handler = subs._make_compile_audit_handler()
        audit = mock.Mock()
        with mock.patch("knowledge.engine.audit.get_audit", return_value=audit):
            handler(FakeEvent(errors=3))
        assert audit.log_compile.call_args.kwargs["result"] == "failure"


class TestCompileMetricsHandler:
    def test_ok(self) -> None:
        handler = subs._make_compile_metrics_handler()
        with mock.patch("knowledge.engine.metrics.record_compile") as record:
            handler(FakeEvent(reason="auto"))
        record.assert_called_once_with(source="auto")


class TestSearchAuditHandler:
    def test_ok(self) -> None:
        handler = subs._make_search_audit_handler()
        audit = mock.Mock()
        event = SimpleNamespace(query="q", docs_returned=3, correlation_id="cid")
        with mock.patch("knowledge.engine.audit.get_audit", return_value=audit):
            handler(event)
        audit.log_read.assert_called_once_with(query="q", docs=3, correlation_id="cid")


class TestArchiveMetricsHandler:
    def test_ok(self) -> None:
        handler = subs._make_archive_metrics_handler()
        event = SimpleNamespace(kind="backup")
        with mock.patch("knowledge.engine.metrics.record_archive") as record:
            handler(event)
        record.assert_called_once_with(kind="backup", status="completed")


class TestLineageSubscriber:
    def test_ok(self, tmp_path) -> None:
        handler = subs._make_lineage_subscriber(tmp_path / "db.sqlite")
        store = mock.Mock()
        with mock.patch("knowledge.engine.lineage_store.SQLiteLineageStore", mock.Mock(return_value=store)):
            handler(FakeEvent())
        store.store_lineage_event.assert_called_once()
        ol = store.store_lineage_event.call_args.args[0]
        assert ol["eventType"] == "COMPLETE"
        assert ol["run"]["runId"] == "cid123"

    def test_error(self, tmp_path) -> None:
        handler = subs._make_lineage_subscriber(tmp_path / "db.sqlite")
        with mock.patch("knowledge.engine.lineage_store.SQLiteLineageStore", mock.Mock(side_effect=OSError("x"))):
            handler(FakeEvent())  # no debe lanzar


class TestVectorIndexSubscriber:
    def test_event_fallido_no_indexa(self, tmp_path) -> None:
        embedder = mock.Mock()
        store = mock.Mock()
        handler = subs._make_vector_index_subscriber(tmp_path / "db.sqlite", embedder, store)
        handler(SimpleNamespace(success=False, asset_id="a1"))
        embedder.embed.assert_not_called()

    def test_asset_no_existe(self, tmp_path) -> None:
        embedder = mock.Mock()
        store = mock.Mock()
        handler = subs._make_vector_index_subscriber(tmp_path / "db.sqlite", embedder, store)
        asset_store = mock.Mock()
        asset_store.get_asset.return_value = None
        with mock.patch("knowledge.engine.asset_store.SQLiteAssetStore", mock.Mock(return_value=asset_store)):
            handler(SimpleNamespace(success=True, asset_id="a1"))
        embedder.embed.assert_not_called()

    def test_ok(self, tmp_path) -> None:
        embedder = mock.Mock()
        embedder.max_input_tokens = 100
        embedder.embed.return_value = [[0.1, 0.2]]
        store = mock.Mock()
        handler = subs._make_vector_index_subscriber(tmp_path / "db.sqlite", embedder, store)
        asset = mock.Mock()
        asset.metadata = {"text_preview": "texto del asset"}
        asset_store = mock.Mock()
        asset_store.get_asset.return_value = asset
        with mock.patch("knowledge.engine.asset_store.SQLiteAssetStore", mock.Mock(return_value=asset_store)):
            handler(SimpleNamespace(success=True, asset_id="a1"))
        embedder.embed.assert_called_once()
        store.upsert.assert_called_once()
        item = store.upsert.call_args.args[0][0]
        assert item.asset_id == "a1"
        assert item.vector == [0.1, 0.2]

    def test_sin_texto(self, tmp_path) -> None:
        embedder = mock.Mock()
        store = mock.Mock()
        handler = subs._make_vector_index_subscriber(tmp_path / "db.sqlite", embedder, store)
        asset = mock.Mock()
        asset.metadata = {}
        asset_store = mock.Mock()
        asset_store.get_asset.return_value = asset
        with mock.patch("knowledge.engine.asset_store.SQLiteAssetStore", mock.Mock(return_value=asset_store)):
            handler(SimpleNamespace(success=True, asset_id="a1"))
        embedder.embed.assert_not_called()


class TestFusionSubscriber:
    def test_ok(self, tmp_path) -> None:
        handler = subs._make_fusion_subscriber(tmp_path / "db.sqlite")
        with mock.patch("knowledge.engine.orchestrator.compile_result_to_claims", mock.Mock(return_value=[mock.Mock()])):
            with mock.patch("motor.core.fusion.run_fusion_on_claims", mock.Mock(return_value=2)):
                with mock.patch("knowledge.engine.metrics.record_fusion") as record:
                    handler(FakeEvent())
        record.assert_called_once()
        assert record.call_args.kwargs["claims"] == 1

    def test_sin_claims(self, tmp_path) -> None:
        handler = subs._make_fusion_subscriber(tmp_path / "db.sqlite")
        with mock.patch("knowledge.engine.orchestrator.compile_result_to_claims", mock.Mock(return_value=[])):
            with mock.patch("knowledge.engine.metrics.record_fusion") as record:
                handler(FakeEvent())
        record.assert_not_called()

    def test_error(self, tmp_path) -> None:
        handler = subs._make_fusion_subscriber(tmp_path / "db.sqlite")
        with mock.patch("knowledge.engine.orchestrator.compile_result_to_claims", mock.Mock(side_effect=OSError("x"))):
            with mock.patch("knowledge.engine.metrics.record_fusion") as record:
                handler(FakeEvent())
        assert record.call_args.kwargs["status"] == "error"


class TestGovernanceSubscriber:
    def test_ok(self, tmp_path) -> None:
        handler = subs._make_governance_subscriber(tmp_path / "db.sqlite")
        store = mock.Mock()
        with mock.patch("knowledge.engine.governance_store.SQLiteGovernanceStore", mock.Mock(return_value=store)):
            handler(FakeEvent(documents_total=5))
        store.set_policy.assert_called_once()
        assert store.set_policy.call_args.kwargs["actor"] == "system"

    def test_sin_documentos(self, tmp_path) -> None:
        handler = subs._make_governance_subscriber(tmp_path / "db.sqlite")
        store = mock.Mock()
        with mock.patch("knowledge.engine.governance_store.SQLiteGovernanceStore", mock.Mock(return_value=store)):
            handler(FakeEvent(documents_total=0))
        store.set_policy.assert_not_called()
