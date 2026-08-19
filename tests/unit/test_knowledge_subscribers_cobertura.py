"""Tests de cobertura para knowledge/engine/subscribers.py."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

import knowledge.engine.subscribers as subs_mod
from knowledge.engine.eventbus import (
    ArchiveCompleted,
    CompileCompleted,
    EventBus,
    MetadataExtracted,
    SearchPerformed,
)
from knowledge.engine.sqlite_writer import init_db
from knowledge.engine.subscribers import (
    _make_archive_metrics_handler,
    _make_compile_archive_handler,
    _make_compile_audit_handler,
    _make_compile_metrics_handler,
    _make_fusion_subscriber,
    _make_governance_subscriber,
    _make_lineage_subscriber,
    _make_search_audit_handler,
    _make_vector_index_subscriber,
    subscribe_all,
)

SCHEMA = Path("schemas/knowledge_graph.sql")


@pytest.fixture(autouse=True)
def _reset_subscribed() -> None:
    subs_mod._SUBSCRIBED = False
    yield
    subs_mod._SUBSCRIBED = False


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "k.db"
    init_db(path, SCHEMA)
    return path


def _compile_event(**kw) -> CompileCompleted:
    return CompileCompleted(
        correlation_id=kw.get("correlation_id", "cid-1"),
        reason=kw.get("reason", "test"),
        documents_changed=kw.get("documents_changed", 3),
        documents_total=kw.get("documents_total", 5),
        errors=kw.get("errors", 0),
    )


def test_subscribe_all_registra_una_vez(monkeypatch) -> None:
    EventBus()
    calls: list[str] = []

    class FakeBus:
        def subscribe(self, topic, handler) -> None:
            calls.append(topic.__name__)

    subscribe_all(FakeBus(), Path("/x"), Path("/y"))  # type: ignore[arg-type]
    first = list(calls)
    subscribe_all(FakeBus(), Path("/x"), Path("/y"))  # type: ignore[arg-type]
    assert calls == first  # idempotente


def test_subscribe_all_con_vectores(monkeypatch) -> None:
    calls: list[str] = []

    class FakeBus:
        def subscribe(self, topic, handler) -> None:
            calls.append(topic.__name__)

    subscribe_all(FakeBus(), Path("/x"), Path("/y"), object(), object())  # type: ignore[arg-type]
    assert "MetadataExtracted" in calls


def test_handler_archive_ok(db, monkeypatch) -> None:
    calls = []

    class FakeJobs:
        def enqueue_archive_job(self, *a, **k):
            calls.append("enqueue")

        def process_archive_jobs(self, *a, **k):
            calls.append("process")

    monkeypatch.setattr("knowledge.engine.jobs.enqueue_archive_job", FakeJobs().enqueue_archive_job)
    monkeypatch.setattr("knowledge.engine.jobs.process_archive_jobs", FakeJobs().process_archive_jobs)
    handler = _make_compile_archive_handler(db, Path("/src"))
    handler(_compile_event())
    assert calls == ["enqueue", "process"]


def test_handler_archive_falla_no_lanza(db, monkeypatch, caplog) -> None:
    monkeypatch.setattr("knowledge.engine.jobs.enqueue_archive_job", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    handler = _make_compile_archive_handler(db, Path("/src"))
    with caplog.at_level(logging.WARNING):
        handler(_compile_event())
    assert "Archive handler failed" in caplog.text


def test_handler_audit_ok(db, monkeypatch) -> None:
    calls = []

    class FakeAudit:
        def log_compile(self, **kw):
            calls.append(kw)

    monkeypatch.setattr("knowledge.engine.audit.get_audit", lambda: FakeAudit())
    handler = _make_compile_audit_handler()
    handler(_compile_event(errors=2))
    assert calls[0]["result"] == "failure"
    handler(_compile_event())
    assert calls[1]["result"] == "success"
    assert calls[1]["docs_changed"] == 3


def test_handler_audit_falla_no_lanza(monkeypatch, caplog) -> None:
    monkeypatch.setattr("knowledge.engine.audit.get_audit", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    handler = _make_compile_audit_handler()
    with caplog.at_level(logging.WARNING):
        handler(_compile_event())
    assert "Audit handler failed" in caplog.text


def test_handler_metrics_ok(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("knowledge.engine.metrics.record_compile", lambda **kw: calls.append(kw))
    handler = _make_compile_metrics_handler()
    handler(_compile_event(reason="cron"))
    assert calls[0] == {"source": "cron"}


def test_handler_metrics_falla_no_lanza(monkeypatch, caplog) -> None:
    monkeypatch.setattr("knowledge.engine.metrics.record_compile", lambda **kw: (_ for _ in ()).throw(RuntimeError("x")))
    handler = _make_compile_metrics_handler()
    with caplog.at_level(logging.WARNING):
        handler(_compile_event())
    assert "Metrics handler failed" in caplog.text


def test_handler_search_audit_ok(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("knowledge.engine.audit.get_audit", lambda: type("A", (), {"log_read": lambda self, **kw: calls.append(kw)})())
    handler = _make_search_audit_handler()
    handler(SearchPerformed(query="q", docs_returned=2, correlation_id="c"))
    assert calls[0]["query"] == "q"
    assert calls[0]["docs"] == 2


def test_handler_search_audit_falla_no_lanza(monkeypatch, caplog) -> None:
    monkeypatch.setattr("knowledge.engine.audit.get_audit", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    handler = _make_search_audit_handler()
    with caplog.at_level(logging.WARNING):
        handler(SearchPerformed(query="q", docs_returned=1, correlation_id="c"))
    assert "Search audit handler failed" in caplog.text


def test_handler_archive_metrics_ok(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("knowledge.engine.metrics.record_archive", lambda **kw: calls.append(kw))
    handler = _make_archive_metrics_handler()
    handler(ArchiveCompleted(kind="git", commit="c1", file_count=2))
    assert calls[0] == {"kind": "git", "status": "completed"}


def test_handler_archive_metrics_falla_no_lanza(monkeypatch, caplog) -> None:
    monkeypatch.setattr("knowledge.engine.metrics.record_archive", lambda **kw: (_ for _ in ()).throw(RuntimeError("x")))
    handler = _make_archive_metrics_handler()
    with caplog.at_level(logging.WARNING):
        handler(ArchiveCompleted(kind="git", commit="c1", file_count=2))
    assert "Archive metrics handler failed" in caplog.text


def test_handler_lineage_ok(db) -> None:
    handler = _make_lineage_subscriber(db)
    handler(_compile_event(correlation_id="cid-lineage"))
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM op_lineage WHERE run_id = 'cid-lineage'").fetchone()[0]
    conn.close()
    assert n == 1


def test_handler_lineage_falla_no_lanza(db, monkeypatch, caplog) -> None:
    class BoomStore:
        def store_lineage_event(self, event) -> bool:
            raise RuntimeError("boom")

    monkeypatch.setattr("knowledge.engine.lineage_store.SQLiteLineageStore", BoomStore)
    handler = _make_lineage_subscriber(db)
    with caplog.at_level(logging.WARNING):
        handler(_compile_event())
    assert "Lineage handler failed" in caplog.text


def test_handler_vector_index_success(db, monkeypatch) -> None:
    class FakeStore:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_asset(self, aid):
            return type("A", (), {"metadata": {"text_preview": "x" * 600}})() if aid == "a1" else None

    class FakeEmbedder:
        max_input_tokens = 100

        def embed(self, texts):
            return [[0.1, 0.2]]

    class FakeVS:
        def __init__(self):
            self.items = []

        def upsert(self, items):
            self.items.extend(items)

    monkeypatch.setattr("knowledge.engine.asset_store.SQLiteAssetStore", FakeStore)
    vs = FakeVS()
    handler = _make_vector_index_subscriber(db, FakeEmbedder(), vs)
    handler(MetadataExtracted(asset_id="a1", asset_type="doc", extractor="test", duration_ms=1, success=True))
    assert len(vs.items) == 1
    assert vs.items[0].asset_id == "a1"
    handler(MetadataExtracted(asset_id="nope", asset_type="doc", extractor="test", duration_ms=1, success=True))
    assert len(vs.items) == 1  # asset None → no op


def test_handler_vector_index_fallos(db, monkeypatch) -> None:
    class FakeStore:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_asset(self, aid):
            return type("A", (), {"metadata": {}})()

    monkeypatch.setattr("knowledge.engine.asset_store.SQLiteAssetStore", FakeStore)
    handler = _make_vector_index_subscriber(db, None, None)  # type: ignore[arg-type]
    handler(MetadataExtracted(asset_id="a1", asset_type="doc", extractor="test", duration_ms=1, success=False))  # success False → return
    handler(MetadataExtracted(asset_id="a1", asset_type="doc", extractor="test", duration_ms=1, success=True))  # text vacío → return


def test_handler_fusion_sin_claims(monkeypatch) -> None:
    monkeypatch.setattr("knowledge.engine.orchestrator.compile_result_to_claims", lambda db: [])
    monkeypatch.setattr("knowledge.engine.metrics.record_fusion", lambda **kw: None)
    handler = _make_fusion_subscriber(Path("/x.db"))
    handler(_compile_event())


def test_handler_fusion_ok(db, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("knowledge.engine.orchestrator.compile_result_to_claims", lambda db: [{"claim": "c1"}])
    monkeypatch.setattr("motor.core.fusion.run_fusion_on_claims", lambda claims, correlation_id: 4)
    monkeypatch.setattr("knowledge.engine.metrics.record_fusion", lambda **kw: calls.append(kw))
    handler = _make_fusion_subscriber(db)
    handler(_compile_event(correlation_id="cid-f"))
    assert calls[0]["claims"] == 1
    assert calls[0]["facts"] == 4


def test_handler_fusion_error(db, monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        "knowledge.engine.orchestrator.compile_result_to_claims",
        lambda db: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    calls = []
    monkeypatch.setattr("knowledge.engine.metrics.record_fusion", lambda **kw: calls.append(kw))
    handler = _make_fusion_subscriber(db)
    with caplog.at_level(logging.WARNING):
        handler(_compile_event())
    assert calls[0]["status"] == "error"
    assert "Fusion handler failed" in caplog.text


def test_handler_governance_ok(db) -> None:
    handler = _make_governance_subscriber(db)
    handler(_compile_event(documents_total=3))
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM op_governance WHERE asset_id = 'compile:cid-1'").fetchone()[0]
    conn.close()
    assert n == 1


def test_handler_governance_sin_docs(db) -> None:
    handler = _make_governance_subscriber(db)
    handler(_compile_event(documents_total=0))


def test_handler_governance_falla_no_lanza(db, monkeypatch, caplog) -> None:
    class BoomStore:
        def set_policy(self, asset_id, policy, actor="system") -> bool:
            raise RuntimeError("boom")

    monkeypatch.setattr("knowledge.engine.governance_store.SQLiteGovernanceStore", BoomStore)
    handler = _make_governance_subscriber(db)
    with caplog.at_level(logging.WARNING):
        handler(_compile_event(documents_total=5))
    assert "Governance handler failed" in caplog.text


def test_handler_vector_index_embed_vacio(db, monkeypatch) -> None:
    class FakeStore:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_asset(self, aid):
            return type("A", (), {"metadata": {"text_preview": "texto corto"}})()

    class FakeEmbedder:
        max_input_tokens = None

        def embed(self, texts):
            return []

    class FakeVS:
        def __init__(self):
            self.items = []

        def upsert(self, items):
            self.items.extend(items)

    monkeypatch.setattr("knowledge.engine.asset_store.SQLiteAssetStore", FakeStore)
    vs = FakeVS()
    handler = _make_vector_index_subscriber(db, FakeEmbedder(), vs)
    handler(MetadataExtracted(asset_id="a1", asset_type="doc", extractor="t", duration_ms=1, success=True))
    assert vs.items == []  # embed vacío → sin upsert


def test_handler_vector_index_falla_no_lanza(db, monkeypatch, caplog) -> None:
    class FakeStore:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_asset(self, aid):
            return type("A", (), {"metadata": {"text_preview": "texto"}})()

    class FakeEmbedder:
        max_input_tokens = 100

        def embed(self, texts):
            raise RuntimeError("embed boom")

    monkeypatch.setattr("knowledge.engine.asset_store.SQLiteAssetStore", FakeStore)
    handler = _make_vector_index_subscriber(db, FakeEmbedder(), object())  # type: ignore[arg-type]
    with caplog.at_level(logging.WARNING):
        handler(MetadataExtracted(asset_id="a1", asset_type="doc", extractor="t", duration_ms=1, success=True))
    assert "Vector index handler failed" in caplog.text
