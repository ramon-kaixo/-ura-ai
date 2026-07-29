from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.pro.tuneladora.pipeline.pending_queue import PendingQueue


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_queue.db"


@pytest.fixture
def queue(db_path: Path) -> PendingQueue:
    return PendingQueue(db_path)


class TestPendingQueue:
    def test_add_returns_id(self, queue: PendingQueue):
        fid = queue.add(archivo="test.py", herramienta="ruff", severidad="high", error_raw="F821")
        assert isinstance(fid, int)
        assert fid > 0

    def test_list_pending(self, queue: PendingQueue):
        queue.add(archivo="a.py", herramienta="ruff", severidad="high", error_raw="E1")
        queue.add(archivo="b.py", herramienta="ruff", severidad="low", error_raw="E2")
        items = queue.list_pending()
        assert len(items) == 2

    def test_list_pending_filter_severity(self, queue: PendingQueue):
        queue.add(archivo="a.py", herramienta="ruff", severidad="high", error_raw="E1")
        queue.add(archivo="b.py", herramienta="ruff", severidad="low", error_raw="E2")
        items = queue.list_pending(severidad="high")
        assert len(items) == 1
        assert items[0]["archivo"] == "a.py"

    def test_resolve(self, queue: PendingQueue):
        fid = queue.add(archivo="a.py", herramienta="ruff", severidad="high", error_raw="E1")
        queue.resolve(fid, estado="hecho")
        items = queue.list_pending()
        assert len(items) == 0

    def test_record_run(self, queue: PendingQueue):
        rid = queue.record_run(mode="check", verdict="OK", seconds=1.5)
        assert isinstance(rid, int)
        assert rid > 0

    def test_stats(self, queue: PendingQueue):
        queue.record_run(mode="check", verdict="OK", seconds=1.0)
        queue.record_run(mode="fix", verdict="FAIL", seconds=2.0)
        s = queue.stats()
        assert s["total_runs"] == 2
        assert s["ok_runs"] == 1
        assert s["fail_runs"] == 1
        assert s["pending_fixes"] == 0

    def test_add_with_estado_imposible(self, queue: PendingQueue):
        fid = queue.add(archivo="x.py", herramienta="ruff", severidad="high", error_raw="no llm", estado="imposible")
        assert fid > 0
        items = queue.list_pending()
        assert len(items) == 0  # 'imposible' no es 'pendiente'

    def test_ok_flag_on_bad_db(self, tmp_path: Path):
        block = tmp_path / "block"
        block.write_text("")  # crear archivo en lugar de dir
        bad_path = block / "queue.db"
        queue = PendingQueue(bad_path)
        assert queue.ok is False
        assert queue.add(archivo="a.py", herramienta="r", severidad="high", error_raw="x") == 0
        assert queue.record_run("check", "OK", 0) == 0
        assert queue.stats() == {"pending_fixes": 0, "total_runs": 0, "ok_runs": 0, "fail_runs": 0}


class TestPendingQueueConcurrency:
    def test_concurrent_add(self, queue: PendingQueue):
        ids = []
        for i in range(5):
            fid = queue.add(archivo=f"f{i}.py", herramienta="ruff", severidad="high", error_raw=f"E{i}")
            ids.append(fid)
        assert len(set(ids)) == 5
        items = queue.list_pending()
        assert len(items) == 5

    def test_db_cleanup(self, db_path: Path):
        q = PendingQueue(db_path)
        q.add(archivo="a.py", herramienta="ruff", severidad="high", error_raw="E1")
        del q
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute("SELECT COUNT(*) FROM pending_fixes").fetchone()[0]
            assert rows == 1
