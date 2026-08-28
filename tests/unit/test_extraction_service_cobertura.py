"""Cobertura 100x100 de knowledge/engine/extraction_service.py (TASK-20260815-003).

Cubre MetadataExtractionService (queue_extract, get_queue_status, start/stop_worker,
_run_extractor, _publish_extracted, extract, extract_path) y las funciones de
módulo (_worker_loop, _claim_next_job*, _esperar_proceso, _process_item,
_extract_in_worker, _write_job_*, _mark_job_failed, _read_job_result) con
mocks de sqlite (FakeConn), registry, store, eventbus y multiprocessing.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

import knowledge.engine.extraction_service as es
from knowledge.engine.eventbus import MetadataExtracted, get_bus
from knowledge.engine.extraction_service import (
    _EXTRACTION_SEMAPHORES,
    MetadataExtractionService,
    _claim_next_job,
    _claim_next_job_fallback,
    _esperar_proceso,
    _extract_in_worker,
    _get_semaphore,
    _guess_mime,
    _mark_job_failed,
    _process_item,
    _read_job_result,
    _worker_loop,
    _write_job_done,
    _write_job_fail,
)
from knowledge.engine.extractors.base import ExtractionResult
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset

_DB = Path("/tmp/extraction-service-test.db")


class FakeRow:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def keys(self) -> Any:
        return self._data.keys()


class FakeConn:
    def __init__(self, responses: dict[str, list[Any]] | None = None) -> None:
        self._responses = responses or {}
        self._raise_on: list[tuple[str, Exception]] = []
        self._current: Any = None
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.lastrowid = 42

    def add_raise(self, pattern: str, exc: Exception) -> None:
        self._raise_on.append((pattern, exc))

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> FakeConn:
        self.executed.append((sql, params))
        for i, (pattern, exc) in enumerate(self._raise_on):
            if pattern in sql:
                del self._raise_on[i]
                raise exc
        self._current = None
        for pattern, results in self._responses.items():
            if pattern in sql and results:
                self._current = results.pop(0)
                break
        return self

    def fetchone(self) -> Any:
        return self._current

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeExtractor:
    id = "fake_extractor"
    version = "1.0.0"
    supported_mime_types: ClassVar[list[str]] = ["text/markdown", "text/plain"]

    def __init__(self, result: ExtractionResult | None = None) -> None:
        self._result = result or ExtractionResult()
        self.last_source: AssetSource | None = None

    def extract(self, source: AssetSource) -> ExtractionResult:
        self.last_source = source
        return self._result


class FakeRegistry:
    def __init__(self, extractors: list[Any] | None = None) -> None:
        self._extractors = extractors or []

    def get_for_mime(self, mime: str) -> list[Any]:
        return [e for e in self._extractors if mime in e.supported_mime_types]


class FakeStore:
    def __init__(self) -> None:
        self.saved: list[Any] = []
        self.result = True

    def save_asset(self, asset: Any) -> bool:
        self.saved.append(asset)
        return self.result


class FakeSem:
    def __init__(self, acquired: bool = True) -> None:
        self._acquired = acquired
        self.acquires = 0
        self.releases = 0

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        self.acquires += 1
        return self._acquired

    def release(self) -> None:
        self.releases += 1


class FakeProc:
    def __init__(
        self,
        alive: bool = True,
        alive_after_join: bool = False,
        alive_after_terminate: bool = False,
    ) -> None:
        self._alive = alive
        self._alive_after_join = alive_after_join
        self._alive_after_terminate = alive_after_terminate
        self.started = False
        self.joins = 0
        self.terminated = 0
        self.killed = 0
        self.closed = False

    def start(self) -> None:
        self.started = True

    def join(self, timeout: float | None = None) -> None:
        self.joins += 1
        if not self._alive_after_join:
            self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    def terminate(self) -> None:
        self.terminated += 1
        if not self._alive_after_terminate:
            self._alive = False

    def kill(self) -> None:
        self.killed += 1
        self._alive = False

    def close(self) -> None:
        self.closed = True


class FakeThread:
    def __init__(self, alive: bool = False) -> None:
        self._alive = alive
        self.joined = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout: float | None = None) -> None:
        self.joined = True


class FakeBusRaising:
    def publish(self, event: Any) -> None:
        raise RuntimeError("bus down")


def _service(
    extractors: list[Any] | None = None,
    store: FakeStore | None = None,
) -> MetadataExtractionService:
    return MetadataExtractionService(
        _DB,
        registry=FakeRegistry(extractors or []),
        store=store or FakeStore(),
    )


def _run_loop_in_thread(
    monkeypatch: pytest.MonkeyPatch,
    conn: FakeConn | None = None,
    stop: threading.Event | None = None,
) -> tuple[threading.Thread, threading.Event]:
    monkeypatch.setattr(es, "_POLL_INTERVAL", 0.01)
    if stop is None:
        stop = threading.Event()
    monkeypatch.setattr(es, "open_db", lambda p: conn if conn is not None else FakeConn())
    thread = threading.Thread(
        target=_worker_loop,
        args=(_DB, FakeRegistry(), FakeStore(), stop, {}, threading.Lock(), 1),
        daemon=True,
    )
    thread.start()
    return thread, stop


class TestGetSemaphore:
    def test_creates_and_reuses(self) -> None:
        _EXTRACTION_SEMAPHORES.clear()
        first = _get_semaphore("ext_a")
        assert _get_semaphore("ext_a") is first
        assert _get_semaphore("ext_b") is not first


class TestGuessMime:
    def test_all_extensions(self) -> None:
        cases = {
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".mdown": "text/markdown",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".avi": "video/avi",
            ".mp3": "audio/mp3",
            ".wav": "audio/wav",
            ".flac": "audio/flac",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".html": "text/html",
            ".htm": "text/html",
        }
        for ext, mime in cases.items():
            assert _guess_mime(f"/tmp/file{ext}") == mime
        assert _guess_mime("/tmp/file.MD") == "text/markdown"

    def test_unknown_and_no_ext(self) -> None:
        assert _guess_mime("/tmp/file.unknownext") == "application/octet-stream"
        assert _guess_mime("/tmp/noext") == "application/octet-stream"


class TestServiceInit:
    def test_defaults(self) -> None:
        service = MetadataExtractionService(_DB)
        assert service._registry is not None
        assert service._store is not None

    def test_provided(self) -> None:
        registry = FakeRegistry()
        store = FakeStore()
        service = MetadataExtractionService(_DB, registry=registry, store=store)
        assert service._registry is registry
        assert service._store is store


class TestQueueExtract:
    def test_insert_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        service = _service()
        job_id = service.queue_extract(AssetSource("filesystem", "/tmp/test.md"))
        assert job_id == "42"
        sql, params = conn.executed[0]
        assert "INSERT INTO op_jobs" in sql
        assert json.loads(params[0]) == {"kind": "filesystem", "location": "/tmp/test.md"}
        assert conn.commits == 1
        assert conn.closed

    def test_integrity_error_row_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({"SELECT id FROM op_jobs": [FakeRow({"id": 3})]})
        conn.add_raise("INSERT INTO op_jobs", sqlite3.IntegrityError("UNIQUE constraint failed"))
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        service = _service()
        assert service.queue_extract(AssetSource("filesystem", "/tmp/test.md")) == "3"
        assert conn.rollbacks == 1
        assert conn.closed

    def test_integrity_error_row_missing_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({"SELECT id FROM op_jobs": [None]})
        conn.add_raise("INSERT INTO op_jobs", sqlite3.IntegrityError("UNIQUE constraint failed"))
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        service = _service()
        assert service.queue_extract(AssetSource("filesystem", "/tmp/test.md")) == "42"
        assert len(conn.executed) == 3
        assert conn.rollbacks == 1
        assert conn.commits == 1
        assert conn.closed


class TestGetQueueStatus:
    def test_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        row = FakeRow(
            {
                "status": "done",
                "error": None,
                "result_data": "{}",
                "started_at": "2026-01-01",
                "completed_at": "2026-01-01",
            }
        )
        conn = FakeConn({"SELECT status, error, result_data": [row]})
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        service = _service()
        status = service.get_queue_status("7")
        assert status["status"] == "done"
        assert status["started_at"] == "2026-01-01"
        assert conn.closed

    def test_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({"SELECT status, error, result_data": [None]})
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        service = _service()
        assert service.get_queue_status("999") == {"status": "not_found"}
        assert conn.closed


class TestStartWorker:
    def test_starts_thread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        started: list[Any] = []

        def recorder(*args: Any) -> None:
            started.append(args)

        monkeypatch.setattr(es, "_worker_loop", recorder)
        service = _service()
        service.start_worker()
        assert service._worker_thread is not None
        assert len(started) == 1
        assert started[0][0] == _DB
        service.stop_worker(timeout=1.0)

    def test_already_alive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: list[Any] = []
        monkeypatch.setattr(threading, "Thread", lambda *a, **k: called.append(a))
        service = _service()
        service._worker_thread = FakeThread(alive=True)
        service.start_worker()
        assert called == []


class TestStopWorker:
    def test_terminate_and_kill(self) -> None:
        service = _service()
        proc = FakeProc(alive_after_join=True, alive_after_terminate=True)
        service._running_jobs = {1: proc}
        service._worker_thread = FakeThread()
        service.stop_worker(timeout=0.1)
        assert proc.terminated == 1
        assert proc.killed == 1
        assert proc.closed
        assert service._worker_stop.is_set()
        assert service._worker_thread.joined

    def test_terminate_only(self) -> None:
        service = _service()
        proc = FakeProc(alive_after_join=True, alive_after_terminate=False)
        service._running_jobs = {1: proc}
        service.stop_worker(timeout=0.1)
        assert proc.terminated == 1
        assert proc.killed == 0
        assert proc.closed

    def test_proc_not_alive(self) -> None:
        service = _service()
        proc = FakeProc(alive=False)
        service._running_jobs = {1: proc}
        service.stop_worker(timeout=0.1)
        assert proc.terminated == 0
        assert proc.killed == 0
        assert proc.closed

    def test_no_thread(self) -> None:
        service = _service()
        service.stop_worker(timeout=0.1)


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


class TestExtractInWorker:
    def _patch_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        conn: FakeConn,
        store: FakeStore,
        extractor: Any | None,
    ) -> None:
        monkeypatch.setattr("knowledge.engine.connection.open_db", lambda p: conn)
        monkeypatch.setattr("knowledge.engine.asset_store.SQLiteAssetStore", lambda p: store)
        monkeypatch.setattr(
            "knowledge.engine.extractors.base.get_registry",
            lambda: SimpleNamespace(get=lambda eid: extractor),
        )

    @staticmethod
    def _failed_error(conn: FakeConn) -> str:
        for sql, params in conn.executed:
            if "status = 'failed'" in sql:
                return params[0]
        raise AssertionError("no failed update found")

    def test_extractor_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()
        self._patch_env(monkeypatch, conn, FakeStore(), extractor=None)
        _extract_in_worker(_DB, 1, "/tmp/a.md", "filesystem", "ghost")
        assert "Extractor ghost not found" in self._failed_error(conn)
        assert conn.commits >= 1
        assert conn.closed

    def test_success_done(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()
        store = FakeStore()
        asset = KnowledgeAsset(asset_id="A9", asset_type=AssetType.MARKDOWN)
        result = ExtractionResult(asset=asset, duration_ms=4.0)
        self._patch_env(monkeypatch, conn, store, extractor=FakeExtractor(result))
        _extract_in_worker(_DB, 1, "/tmp/a.md", "filesystem", "fake_extractor")
        assert any("status = 'done'" in sql for sql, _ in conn.executed)
        assert len(store.saved) == 1
        assert conn.closed

    def test_save_false_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()
        store = FakeStore()
        store.result = False
        asset = KnowledgeAsset(asset_id="A9", asset_type=AssetType.MARKDOWN)
        result = ExtractionResult(asset=asset)
        self._patch_env(monkeypatch, conn, store, extractor=FakeExtractor(result))
        _extract_in_worker(_DB, 1, "/tmp/a.md", "filesystem", "fake_extractor")
        assert "AssetStore.save_asset() returned False" in self._failed_error(conn)
        assert conn.closed

    def test_errors_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()
        result = ExtractionResult(errors=["bad pdf"])
        self._patch_env(monkeypatch, conn, FakeStore(), extractor=FakeExtractor(result))
        _extract_in_worker(_DB, 1, "/tmp/a.pdf", "filesystem", "fake_extractor")
        assert self._failed_error(conn) == "bad pdf"
        assert conn.closed

    def test_extractor_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()

        class BoomExtractor(FakeExtractor):
            def extract(self, source: AssetSource) -> ExtractionResult:
                raise RuntimeError("boom")

        self._patch_env(monkeypatch, conn, FakeStore(), extractor=BoomExtractor())
        _extract_in_worker(_DB, 1, "/tmp/a.pdf", "filesystem", "fake_extractor")
        assert self._failed_error(conn) == "boom"
        assert conn.closed

    def test_save_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()

        class RaisingStore(FakeStore):
            def save_asset(self, asset: Any) -> bool:
                raise RuntimeError("disk full")

        asset = KnowledgeAsset(asset_id="A9", asset_type=AssetType.MARKDOWN)
        result = ExtractionResult(asset=asset)
        self._patch_env(monkeypatch, conn, RaisingStore(), extractor=FakeExtractor(result))
        _extract_in_worker(_DB, 1, "/tmp/a.md", "filesystem", "fake_extractor")
        assert self._failed_error(conn) == "disk full"
        assert conn.closed

    def test_open_db_raises_without_conn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_open_db(path: Path) -> None:
            raise RuntimeError("cannot open db")

        monkeypatch.setattr("knowledge.engine.connection.open_db", raise_open_db)
        _extract_in_worker(_DB, 1, "/tmp/a.md", "filesystem", "fake_extractor")


class TestWriteJobs:
    def test_write_job_done(self) -> None:
        conn = FakeConn()
        _write_job_done(conn, 7, "A1", "markdown", 2.5)
        sql, params = conn.executed[-1]
        assert "status = 'done'" in sql
        assert json.loads(params[0]) == {"asset_id": "A1", "asset_type": "markdown", "duration_ms": 2.5}
        assert conn.commits == 1

    def test_write_job_fail(self) -> None:
        conn = FakeConn()
        _write_job_fail(conn, 7, "oops")
        sql, params = conn.executed[-1]
        assert "status = 'failed'" in sql
        assert params[0] == "oops"
        assert conn.commits == 1

    def test_mark_job_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        _mark_job_failed(_DB, 7, "nope")
        sql, params = conn.executed[-1]
        assert "status = 'failed'" in sql
        assert params[0] == "nope"
        assert conn.closed


class TestReadJobResult:
    def test_row_merged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        row = FakeRow(
            {
                "status": "done",
                "result_data": '{"asset_id": "A1", "asset_type": "markdown", "duration_ms": 3.0}',
                "error": "warn",
            }
        )
        conn = FakeConn({"SELECT status, result_data, error": [row]})
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        result = _read_job_result(_DB, 1)
        assert result == {"status": "done", "asset_id": "A1", "asset_type": "markdown", "duration_ms": 3.0, "error": "warn"}
        assert conn.closed

    def test_row_minimal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        row = FakeRow({"status": "running", "result_data": None, "error": None})
        conn = FakeConn({"SELECT status, result_data, error": [row]})
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        assert _read_job_result(_DB, 1) == {"status": "running"}
        assert conn.closed

    def test_no_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({"SELECT status, result_data, error": [None]})
        monkeypatch.setattr(es, "open_db", lambda p: conn)
        assert _read_job_result(_DB, 1) is None
        assert conn.closed


class TestWorkerLoop:
    def test_stop_pre_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: list[Any] = []
        monkeypatch.setattr(es, "open_db", lambda p: called.append(p) or FakeConn())
        stop = threading.Event()
        stop.set()
        _worker_loop(_DB, FakeRegistry(), FakeStore(), stop, {}, threading.Lock(), 1)
        assert called == []

    def test_no_job_then_stop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({"UPDATE op_jobs": [None]})
        thread, stop = _run_loop_in_thread(monkeypatch, conn)
        time.sleep(0.05)
        stop.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert conn.rollbacks >= 1
        assert any("UPDATE op_jobs" in sql for sql, _ in conn.executed)

    def test_claim_success_processes_job(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stop = threading.Event()
        processed: list[Any] = []

        def fake_process(*args: Any) -> None:
            processed.append(args)
            stop.set()

        monkeypatch.setattr(es, "_claim_next_job", lambda conn: FakeRow({"id": 1, "payload": "{}"}))
        monkeypatch.setattr(es, "_process_item", fake_process)
        conn = FakeConn()
        thread, stop = _run_loop_in_thread(monkeypatch, conn, stop)
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert len(processed) == 1
        assert conn.commits >= 1
        assert conn.closed

    def test_operational_error_fallback_processes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stop = threading.Event()
        processed: list[Any] = []

        def fake_process(*args: Any) -> None:
            processed.append(args)
            stop.set()

        def raise_operational(*args: Any) -> None:
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(es, "_claim_next_job", raise_operational)
        monkeypatch.setattr(es, "_claim_next_job_fallback", lambda conn: FakeRow({"id": 2, "payload": "{}"}))
        monkeypatch.setattr(es, "_process_item", fake_process)
        conn = FakeConn()
        thread, stop = _run_loop_in_thread(monkeypatch, conn, stop)
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert len(processed) == 1
        assert conn.rollbacks >= 1

    def test_operational_error_fallback_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(es, "_POLL_INTERVAL", 0.01)
        stop = threading.Event()
        conns: list[FakeConn] = []
        monkeypatch.setattr(es, "open_db", lambda p: conns.append(FakeConn()) or conns[-1])

        def raise_operational(*args: Any) -> None:
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(es, "_claim_next_job", raise_operational)
        monkeypatch.setattr(es, "_claim_next_job_fallback", lambda conn: None)
        thread = threading.Thread(
            target=_worker_loop,
            args=(_DB, FakeRegistry(), FakeStore(), stop, {}, threading.Lock(), 1),
            daemon=True,
        )
        thread.start()
        time.sleep(0.05)
        stop.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert len(conns) >= 2

    def test_begin_immediate_error_closes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()
        conn.add_raise("BEGIN IMMEDIATE", sqlite3.OperationalError("boom"))
        thread, stop = _run_loop_in_thread(monkeypatch, conn)
        time.sleep(0.05)
        stop.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert conn.closed

    def test_open_db_raises_logged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(es, "_POLL_INTERVAL", 0.01)
        stop = threading.Event()

        def raise_open_db(path: Path) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(es, "open_db", raise_open_db)
        thread = threading.Thread(
            target=_worker_loop,
            args=(_DB, FakeRegistry(), FakeStore(), stop, {}, threading.Lock(), 1),
            daemon=True,
        )
        thread.start()
        time.sleep(0.05)
        stop.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
