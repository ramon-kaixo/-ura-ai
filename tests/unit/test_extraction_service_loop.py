"""Tests cobertura extraction_service — worker loop (split)."""
from __future__ import annotations

from _extraction_helpers import (  # noqa: F401
    _DB,
    Any,
    AssetSource,
    AssetType,
    ExtractionResult,
    FakeConn,
    FakeExtractor,
    FakeRegistry,
    FakeRow,
    FakeStore,
    KnowledgeAsset,
    Path,
    SimpleNamespace,
    _claim_next_job,
    _claim_next_job_fallback,
    _extract_in_worker,
    _mark_job_failed,
    _process_item,
    _read_job_result,
    _run_loop_in_thread,
    _worker_loop,
    _write_job_done,
    _write_job_fail,
    es,
    json,
    pytest,
    sqlite3,
    threading,
    time,
)


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
