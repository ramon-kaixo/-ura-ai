"""Tests for SnapshotManager (scripts/pro/tuneladora/pipeline/snapshot_manager.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pro.tuneladora.pipeline.snapshot_manager import SnapshotManager


@pytest.fixture
def snap(tmp_path: Path) -> SnapshotManager:
    return SnapshotManager(tmp_path)


class TestSnapshotManagerInit:
    def test_ok_flag_on_normal_path(self, tmp_path: Path):
        sm = SnapshotManager(tmp_path)
        assert sm.ok is True
        assert (tmp_path / "snapshots").exists()

    def test_ok_flag_on_bad_path(self):
        sm = SnapshotManager(Path("/nonexistent/deep/dir"))
        assert sm.ok is False


class TestSnapshotManagerTake:
    def test_take_single_file(self, snap: SnapshotManager, tmp_path: Path):
        src = tmp_path / "test.py"
        src.write_text("x = 1")
        result = snap.take("test_label", [src])
        assert result is not None
        assert result.exists()
        assert (result / "meta.json").exists()

    def test_take_no_files(self, snap: SnapshotManager):
        result = snap.take("empty", [])
        assert result is not None
        meta_file = result / "meta.json"
        meta = json.loads(meta_file.read_text())
        assert meta["count"] == 0

    def test_take_nonexistent_file(self, snap: SnapshotManager, tmp_path: Path):
        result = snap.take("missing", [tmp_path / "ghost.py"])
        meta = json.loads((result / "meta.json").read_text())
        assert meta["count"] == 0

    def test_take_multiple_files(self, snap: SnapshotManager, tmp_path: Path):
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("a")
        b.write_text("b")
        result = snap.take("multi", [a, b])
        meta = json.loads((result / "meta.json").read_text())
        assert meta["count"] == 2

    def test_take_empty_label(self, snap: SnapshotManager, tmp_path: Path):
        src = tmp_path / "f.py"
        src.write_text("code")
        result = snap.take("", [src])
        assert result is not None
        assert result.exists()


class TestSnapshotManagerRestore:
    def test_restore_meta_written(self, snap: SnapshotManager, tmp_path: Path):
        work = tmp_path / "sub"
        work.mkdir()
        src = work / "original.py"
        src.write_text("original")
        snap_path = snap.take("restore_test", [src])
        assert snap_path is not None
        meta = json.loads((snap_path / "meta.json").read_text())
        assert meta["count"] == 1
        assert meta["label"] == "restore_test"

    def test_restore_nonexistent(self, snap: SnapshotManager):
        ok = snap.restore(Path("/nonexistent_snapshot"))
        assert ok is False

    def test_restore_missing_meta(self, snap: SnapshotManager, tmp_path: Path):
        empty_dir = tmp_path / "empty_snap"
        empty_dir.mkdir()
        ok = snap.restore(empty_dir)
        assert ok is False


class TestSnapshotManagerLatest:
    def test_latest_empty(self, snap: SnapshotManager):
        assert snap.latest() is None

    def test_latest_order(self, snap: SnapshotManager, tmp_path: Path):
        src = tmp_path / "f.py"
        src.write_text("code")
        snap.take("first", [src])
        snap2 = snap.take("second", [src])
        latest = snap.latest()
        assert latest is not None
        assert latest.name == snap2.name


class TestSnapshotManagerPrune:
    def test_prune_empty(self, snap: SnapshotManager):
        assert snap.prune(keep=5) == 0

    def test_prune_keeps_n(self, snap: SnapshotManager, tmp_path: Path):
        src = tmp_path / "f.py"
        src.write_text("code")
        for i in range(10):
            snap.take(f"snap_{i}", [src])
        removed = snap.prune(keep=3)
        assert removed > 0
        remaining = sorted((tmp_path / "snapshots").iterdir()) if (tmp_path / "snapshots").exists() else []
        assert len(remaining) <= 3
