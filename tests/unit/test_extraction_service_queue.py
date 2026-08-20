"""Tests cobertura extraction_service — queue/worker lifecycle (split)."""
from __future__ import annotations

from _extraction_helpers import (  # noqa: F401
    _DB,
    _EXTRACTION_SEMAPHORES,
    Any,
    AssetSource,
    FakeConn,
    FakeProc,
    FakeRegistry,
    FakeRow,
    FakeStore,
    FakeThread,
    MetadataExtractionService,
    _get_semaphore,
    _guess_mime,
    _service,
    _worker_loop,
    es,
    json,
    pytest,
    sqlite3,
    threading,
)


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


