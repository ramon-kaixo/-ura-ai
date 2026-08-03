"""Tests para knowledge/engine/snapshot_store.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from knowledge.engine.models import Snapshot, SourceObject
from knowledge.engine.snapshot_store import (
    clear_snapshot,
    load_last_commit,
    load_snapshot,
    save_snapshot,
)


@pytest.fixture(autouse=True)
def tmp_snapshot_paths(monkeypatch, tmp_path):
    import knowledge.engine.snapshot_store as ss

    dirs = tmp_path / ".nervioso"
    monkeypatch.setattr(ss, "_NERVIOSO_DIR", dirs)
    monkeypatch.setattr(ss, "_SNAPSHOT_FILE", dirs / "last_snapshot.json")
    monkeypatch.setattr(ss, "_COMMIT_FILE", dirs / "last_commit.txt")
    yield


def _snapshot() -> Snapshot:
    return Snapshot(
        sources=(
            SourceObject(id="s1", path="a.md", kind="markdown", content_sha256="abc", size=10),
            SourceObject(id="s2", path="b.yaml", kind="yaml", content_sha256="def", size=20),
        ),
        taken_at="2026-01-01T00:00:00",
    )


class TestSaveSnapshot:
    def test_save_crea_archivos(self) -> None:
        save_snapshot(_snapshot(), commit="abc123def456")
        snap = json.loads(Path(load_snapshot.__globals__["_SNAPSHOT_FILE"]).read_text())
        assert len(snap["sources"]) == 2
        assert snap["sources"][0]["id"] == "s1"
        assert Path(load_last_commit.__globals__["_COMMIT_FILE"]).read_text() == "abc123def456"

    def test_save_default_commit(self) -> None:
        save_snapshot(_snapshot())
        assert load_last_commit() == "HEAD"


class TestLoadSnapshot:
    def test_sin_snapshot(self) -> None:
        assert load_snapshot() is None

    def test_roundtrip(self) -> None:
        save_snapshot(_snapshot())
        snap = load_snapshot()
        assert snap is not None
        assert len(snap.sources) == 2
        assert snap.sources[0].content_sha256 == "abc"
        assert snap.sources[1].kind == "yaml"
        assert snap.taken_at == "2026-01-01T00:00:00"

    def test_json_corrupto(self) -> None:
        import knowledge.engine.snapshot_store as ss

        ss._NERVIOSO_DIR.mkdir(parents=True, exist_ok=True)
        ss._SNAPSHOT_FILE.write_text("no es json")
        assert load_snapshot() is None

    def test_key_faltante(self) -> None:
        import knowledge.engine.snapshot_store as ss

        ss._NERVIOSO_DIR.mkdir(parents=True, exist_ok=True)
        ss._SNAPSHOT_FILE.write_text(json.dumps({"sources": [{"id": "s1"}]}))  # falta path/sha
        assert load_snapshot() is None


class TestLoadLastCommit:
    def test_sin_commit(self) -> None:
        assert load_last_commit() is None

    def test_con_commit(self) -> None:
        import knowledge.engine.snapshot_store as ss

        ss._NERVIOSO_DIR.mkdir(parents=True, exist_ok=True)
        ss._COMMIT_FILE.write_text("  commit123  ")
        assert load_last_commit() == "commit123"


class TestClearSnapshot:
    def test_limpia(self) -> None:
        save_snapshot(_snapshot())
        clear_snapshot()
        assert load_snapshot() is None
        assert load_last_commit() is None

    def test_limpia_sin_archivos(self) -> None:
        clear_snapshot()  # no debe lanzar
