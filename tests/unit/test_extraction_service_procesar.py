"""Tests cobertura extraction_service — procesamiento (split)."""
from __future__ import annotations

from _extraction_helpers import (  # noqa: F401
    _DB,
    _EXTRACTION_SEMAPHORES,
    Any,
    AssetSource,
    AssetType,
    ExtractionResult,
    FakeBusRaising,
    FakeConn,
    FakeExtractor,
    FakeProc,
    FakeRegistry,
    FakeRow,
    FakeSem,
    FakeStore,
    KnowledgeAsset,
    MetadataExtracted,
    Path,
    SimpleNamespace,
    _claim_next_job,
    _claim_next_job_fallback,
    _esperar_proceso,
    _get_semaphore,
    _mark_job_failed,
    _process_item,
    _read_job_result,
    _service,
    es,
    get_bus,
    json,
    pytest,
    threading,
)


class TestRunExtractor:
    def test_errors_return_none(self) -> None:
        ext = FakeExtractor(ExtractionResult(errors=["err1"]))
        service = _service()
        assert service._run_extractor(ext, AssetSource("filesystem", "/tmp/a.md")) is None

    def test_no_asset(self) -> None:
        ext = FakeExtractor(ExtractionResult())
        service = _service()
        assert service._run_extractor(ext, AssetSource("filesystem", "/tmp/a.md")) is None

    def test_saved_publishes(self) -> None:
        captured: list[Any] = []
        handler = captured.append
        bus = get_bus()
        bus.subscribe(MetadataExtracted, handler)
        try:
            asset = KnowledgeAsset(asset_id="A1", asset_type=AssetType.PDF)
            ext = FakeExtractor(ExtractionResult(asset=asset, duration_ms=1.5))
            service = _service()
            out = service._run_extractor(ext, AssetSource("filesystem", "/tmp/a.pdf"))
            assert out is not None
            assert out["asset_id"] == "A1"
            assert out["saved"] is True
            assert out["duration_ms"] == 1.5
            assert len(captured) == 1
            assert captured[0].asset_type == AssetType.PDF
            assert captured[0].extractor == "fake_extractor"
        finally:
            bus.unsubscribe(MetadataExtracted, handler)

    def test_not_saved_no_publish(self) -> None:
        store = FakeStore()
        store.result = False
        asset = KnowledgeAsset(asset_id="A1", asset_type=AssetType.PDF)
        ext = FakeExtractor(ExtractionResult(asset=asset, duration_ms=1.5))
        service = _service(store=store)
        out = service._run_extractor(ext, AssetSource("filesystem", "/tmp/a.pdf"))
        assert out is not None
        assert out["saved"] is False
        assert out["asset_id"] == "A1"



class TestPublishExtracted:
    def test_publish_ok(self) -> None:
        captured: list[Any] = []
        handler = captured.append
        bus = get_bus()
        bus.subscribe(MetadataExtracted, handler)
        try:
            asset = KnowledgeAsset(asset_id="A1", asset_type=AssetType.VIDEO)
            service = _service()
            service._publish_extracted(asset, "ext1", 2.0)
            assert len(captured) == 1
            assert captured[0].duration_ms == 2.0
            assert captured[0].asset_id == "A1"
        finally:
            bus.unsubscribe(MetadataExtracted, handler)

    def test_publish_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(es, "get_bus", lambda: FakeBusRaising())
        asset = KnowledgeAsset(asset_id="A1", asset_type=AssetType.VIDEO)
        service = _service()
        service._publish_extracted(asset, "ext1", 2.0)



class TestExtract:
    def test_no_extractors(self) -> None:
        service = _service()
        out = service.extract(AssetSource("filesystem", "/tmp/a.xyz"))
        assert out == {"success": False, "error": "No extractor for application/octet-stream", "asset": None}

    def test_all_fail(self) -> None:
        ext = FakeExtractor(ExtractionResult(errors=["e"]))
        service = _service([ext])
        out = service.extract(AssetSource("filesystem", "/tmp/a.md"))
        assert out == {"success": False, "results": [], "asset": None}

    def test_one_succeeds(self) -> None:
        asset = KnowledgeAsset(asset_id="A1", asset_type=AssetType.MARKDOWN)
        ext = FakeExtractor(ExtractionResult(asset=asset, duration_ms=1.0))
        service = _service([ext])
        out = service.extract(AssetSource("filesystem", "/tmp/a.md"))
        assert out["success"] is True
        assert out["results"][0]["asset_id"] == "A1"
        assert out["asset"] == "A1"

    def test_partial_success(self) -> None:
        bad = FakeExtractor(ExtractionResult(errors=["boom"]))
        asset = KnowledgeAsset(asset_id="A2", asset_type=AssetType.MARKDOWN)
        good = FakeExtractor(ExtractionResult(asset=asset))
        service = _service([bad, good])
        out = service.extract(AssetSource("filesystem", "/tmp/a.md"))
        assert out["success"] is True
        assert len(out["results"]) == 1
        assert out["asset"] == "A2"

    def test_extract_path(self) -> None:
        asset = KnowledgeAsset(asset_id="A1", asset_type=AssetType.MARKDOWN)
        ext = FakeExtractor(ExtractionResult(asset=asset))
        service = _service([ext])
        out = service.extract_path(Path("/tmp/doc.md"))
        assert out["success"] is True
        assert ext.last_source is not None
        assert ext.last_source.kind == "filesystem"
        assert ext.last_source.location == "/tmp/doc.md"



class TestClaimNextJob:
    def test_returns_row(self) -> None:
        conn = FakeConn({"UPDATE op_jobs": [FakeRow({"id": 9})]})
        row = _claim_next_job(conn)
        assert row is not None
        assert row["id"] == 9
        assert any("RETURNING id, payload" in sql for sql, _ in conn.executed)

    def test_returns_none(self) -> None:
        conn = FakeConn({"UPDATE op_jobs": [None]})
        assert _claim_next_job(conn) is None



class TestClaimNextJobFallback:
    def test_returns_row_and_updates(self) -> None:
        conn = FakeConn({"SELECT id, payload": [FakeRow({"id": 5, "payload": "p"})]})
        row = _claim_next_job_fallback(conn)
        assert row is not None
        assert row["id"] == 5
        assert any("UPDATE op_jobs SET status = 'running'" in sql for sql, _ in conn.executed)

    def test_returns_none(self) -> None:
        conn = FakeConn({"SELECT id, payload": [None]})
        assert _claim_next_job_fallback(conn) is None
        assert len(conn.executed) == 1



class TestEsperarProceso:
    def test_done_publishes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[Any] = []
        handler = captured.append
        bus = get_bus()
        bus.subscribe(MetadataExtracted, handler)
        try:
            monkeypatch.setattr(
                es,
                "_read_job_result",
                lambda db, jid: {"status": "done", "asset_id": "A1", "asset_type": "markdown", "duration_ms": 3.2},
            )
            proc = FakeProc()
            running = {1: proc}
            result = _esperar_proceso(_DB, 1, "ext1", proc, running, threading.Lock())
            assert result == {"status": "done", "asset_id": "A1", "asset_type": "markdown", "duration_ms": 3.2}
            assert running == {}
            assert len(captured) == 1
            assert captured[0].asset_id == "A1"
            assert captured[0].extractor == "ext1"
            assert captured[0].success is True
            assert captured[0].asset_type == AssetType.MARKDOWN
        finally:
            bus.unsubscribe(MetadataExtracted, handler)

    def test_failed_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(es, "_read_job_result", lambda db, jid: {"status": "failed"})
        proc = FakeProc()
        running = {1: proc}
        assert _esperar_proceso(_DB, 1, "ext1", proc, running, threading.Lock()) is None
        assert running == {}
        assert proc.joins == 1

    def test_no_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(es, "_read_job_result", lambda db, jid: None)
        proc = FakeProc()
        running = {1: proc}
        assert _esperar_proceso(_DB, 1, "ext1", proc, running, threading.Lock()) is None
        assert running == {}

    def test_timeout_kill(self, monkeypatch: pytest.MonkeyPatch) -> None:
        marked: list[Any] = []
        monkeypatch.setattr(es, "_mark_job_failed", lambda db, jid, err: marked.append((jid, err)))
        proc = FakeProc(alive_after_join=True, alive_after_terminate=True)
        running = {1: proc}
        assert _esperar_proceso(_DB, 1, "ext1", proc, running, threading.Lock()) is None
        assert proc.terminated == 1
        assert proc.killed == 1
        assert marked == [(1, "timeout after 300s")]
        assert running == {}

    def test_timeout_terminate_sufficient(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(es, "_mark_job_failed", lambda db, jid, err: None)
        proc = FakeProc(alive_after_join=True, alive_after_terminate=False)
        running = {1: proc}
        assert _esperar_proceso(_DB, 1, "ext1", proc, running, threading.Lock()) is None
        assert proc.terminated == 1
        assert proc.killed == 0
        assert running == {}

    def test_publish_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            es,
            "_read_job_result",
            lambda db, jid: {"status": "done", "asset_id": "A1", "asset_type": "pdf", "duration_ms": 1.0},
        )
        monkeypatch.setattr(es, "get_bus", lambda: FakeBusRaising())
        proc = FakeProc()
        running = {1: proc}
        result = _esperar_proceso(_DB, 1, "ext1", proc, running, threading.Lock())
        assert result is not None
        assert result["asset_id"] == "A1"
        assert running == {}



class TestProcessItem:
    def test_no_extractors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        marked: list[Any] = []
        monkeypatch.setattr(es, "_mark_job_failed", lambda db, jid, err: marked.append((jid, err)))
        row = FakeRow({"id": 3, "payload": json.dumps({"kind": "filesystem", "location": "/tmp/a.md"})})
        _process_item(_DB, FakeRegistry(), {}, threading.Lock(), row)
        assert marked == [(3, "No extractor for text/markdown")]

    def test_semaphore_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        marked: list[Any] = []
        monkeypatch.setattr(es, "_mark_job_failed", lambda db, jid, err: marked.append((jid, err)))
        sem = FakeSem(acquired=False)
        monkeypatch.setattr(es, "_get_semaphore", lambda eid: sem)
        ext = FakeExtractor()
        row = FakeRow({"id": 3, "payload": json.dumps({"kind": "filesystem", "location": "/tmp/a.md"})})
        _process_item(_DB, FakeRegistry([ext]), {}, threading.Lock(), row)
        assert marked == [(3, "Semaphore timeout for fake_extractor")]
        assert sem.acquires == 1

    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _EXTRACTION_SEMAPHORES.clear()
        waited: list[Any] = []

        def fake_esperar(
            db_path: Path,
            job_id: int,
            extractor_id: str,
            proc: Any,
            running_jobs: dict,
            jobs_lock: threading.Lock,
        ) -> None:
            waited.append((job_id, extractor_id, dict(running_jobs)))

        monkeypatch.setattr(es, "_esperar_proceso", fake_esperar)
        proc = FakeProc()
        monkeypatch.setattr(es, "multiprocessing", SimpleNamespace(Process=lambda *a, **k: proc))
        ext = FakeExtractor()
        row = FakeRow({"id": 3, "payload": json.dumps({"kind": "filesystem", "location": "/tmp/a.md"})})
        running: dict[int, Any] = {}
        _process_item(_DB, FakeRegistry([ext]), running, threading.Lock(), row)
        assert proc.started
        assert waited == [(3, "fake_extractor", {3: proc})]
        assert running == {3: proc}
        assert proc.joins == 1
        assert proc.closed
        assert _get_semaphore("fake_extractor")._value == 1

    def test_process_creation_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _EXTRACTION_SEMAPHORES.clear()
        sem = FakeSem()
        monkeypatch.setattr(es, "_get_semaphore", lambda eid: sem)

        def raise_process(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("cannot fork")

        monkeypatch.setattr(es, "multiprocessing", SimpleNamespace(Process=raise_process))
        ext = FakeExtractor()
        row = FakeRow({"id": 3, "payload": json.dumps({"kind": "filesystem", "location": "/tmp/a.md"})})
        with pytest.raises(RuntimeError, match="cannot fork"):
            _process_item(_DB, FakeRegistry([ext]), {}, threading.Lock(), row)
        assert sem.releases == 1


