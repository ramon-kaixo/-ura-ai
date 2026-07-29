"""Tests for EpisodicMemory (scripts/pro/tuneladora/memory/episodic.py)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.pro.tuneladora.memory.episodic import Episode, EpisodicMemory


@pytest.fixture
def ep_mem(tmp_path: Path) -> EpisodicMemory:
    return EpisodicMemory(tmp_path / "test_episodic.db")


def make_ep(ep_id: str, pipeline: str = "test", status: str = "completed") -> Episode:
    now = datetime.now(UTC).isoformat()
    return Episode(
        episode_id=ep_id, pipeline=pipeline, status=status,
        started=now, finished=now, summary="ok", duration_ms=100,
    )


class TestRecord:
    def test_record_and_get(self, ep_mem: EpisodicMemory) -> None:
        ep = make_ep("ep1")
        ep_mem.record(ep)
        got = ep_mem.get("ep1")
        assert got is not None
        assert got.status == "completed"
        assert got.pipeline == "test"

    def test_get_missing(self, ep_mem: EpisodicMemory) -> None:
        assert ep_mem.get("nope") is None

    def test_record_failure(self, ep_mem: EpisodicMemory) -> None:
        ep = make_ep("fail1", status="failed")
        ep_mem.record(ep)
        got = ep_mem.get("fail1")
        assert got and got.status == "failed"


class TestList:
    def test_list_recent(self, ep_mem: EpisodicMemory) -> None:
        ep_mem.record(make_ep("a", pipeline="p1"))
        ep_mem.record(make_ep("b", pipeline="p2"))
        assert len(ep_mem.list_recent()) == 2

    def test_list_recent_by_pipeline(self, ep_mem: EpisodicMemory) -> None:
        ep_mem.record(make_ep("a", pipeline="health"))
        ep_mem.record(make_ep("b", pipeline="cleanup"))
        results = ep_mem.list_recent(pipeline="health")
        assert len(results) == 1
        assert results[0].episode_id == "a"

    def test_list_failures(self, ep_mem: EpisodicMemory) -> None:
        ep_mem.record(make_ep("ok1"))
        ep_mem.record(make_ep("fail1", status="failed"))
        ep_mem.record(make_ep("fail2", status="failed", pipeline="health"))
        assert len(ep_mem.list_failures()) == 2
        assert len(ep_mem.list_failures(pipeline="health")) == 1


class TestCleanup:
    def test_delete_old(self, ep_mem: EpisodicMemory) -> None:
        old_early = Episode(
            episode_id="old", pipeline="p", status="completed",
            started="2020-01-01T00:00:00", finished="2020-01-01T00:00:01",
            duration_ms=0,
        )
        ep_mem.record(old_early)
        ep_mem.record(make_ep("new"))
        deleted = ep_mem.delete_old("2025-01-01T00:00:00")
        assert deleted == 1
        assert ep_mem.get("new") is not None

    def test_count_failures(self, ep_mem: EpisodicMemory) -> None:
        ep_mem.record(make_ep("a", status="failed"))
        ep_mem.record(make_ep("b", status="failed"))
        ep_mem.record(make_ep("c"))
        assert ep_mem.count_failures(since_hours=24) == 2
