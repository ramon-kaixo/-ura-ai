"""Tests for UnifiedScheduler (scripts/pro/tuneladora/unified_scheduler.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.pro.tuneladora.unified_scheduler import UnifiedPipeline, UnifiedScheduler


@pytest.fixture
def scheduler(tmp_path: Path) -> UnifiedScheduler:
    return UnifiedScheduler(nervioso=tmp_path)


class TestRegistration:
    def test_register_pipeline(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="test", handler=lambda: {"status": "ok"})
        scheduler.register(p)
        assert scheduler.get_pipeline("test") is p

    def test_unregister(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="x", handler=lambda: {})
        scheduler.register(p)
        scheduler.unregister("x")
        assert scheduler.get_pipeline("x") is None

    def test_list_pipelines_ordered(self, scheduler: UnifiedScheduler) -> None:
        p1 = UnifiedPipeline(name="low", handler=lambda: {}, priority=20)
        p2 = UnifiedPipeline(name="high", handler=lambda: {}, priority=5)
        scheduler.register(p1)
        scheduler.register(p2)
        plist = scheduler.list_pipelines()
        assert plist[0].name == "high"
        assert plist[1].name == "low"


class TestRunPipeline:
    def test_run_pipeline_success(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="ok", handler=lambda: {"summary": "done"})
        scheduler.register(p)
        result = scheduler.run_pipeline("ok")
        assert result["_status"] == "completed"

    def test_run_pipeline_disabled(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="off", handler=lambda: {}, enabled=False)
        scheduler.register(p)
        result = scheduler.run_pipeline("off")
        assert result["status"] == "skipped"

    def test_run_pipeline_missing(self, scheduler: UnifiedScheduler) -> None:
        result = scheduler.run_pipeline("nope")
        assert "error" in result

    def test_run_pipeline_error(self, scheduler: UnifiedScheduler) -> None:
        def failing() -> dict:
            msg = "intentional error"
            raise RuntimeError(msg)

        p = UnifiedPipeline(name="fail", handler=failing)
        scheduler.register(p)
        result = scheduler.run_pipeline("fail")
        assert result["_status"] == "failed"
        assert "intentional error" in result["error"]

    def test_circuit_breaker_trips(self, scheduler: UnifiedScheduler) -> None:
        def failing() -> dict:
            raise RuntimeError("epic fail")

        p = UnifiedPipeline(name="bomb", handler=failing)
        scheduler.register(p)
        scheduler._max_failures = 2
        for _ in range(2):
            scheduler.run_pipeline("bomb")
        result = scheduler.run_pipeline("bomb")
        assert result["status"] == "circuit_open"

    def test_circuit_reset(self, scheduler: UnifiedScheduler) -> None:
        def failing() -> dict:
            raise RuntimeError("fail")

        p = UnifiedPipeline(name="bomb", handler=failing)
        scheduler.register(p)
        scheduler._max_failures = 1
        scheduler.run_pipeline("bomb")
        scheduler.reset_circuit("bomb")
        result = scheduler.run_pipeline("bomb")
        assert result["_status"] == "failed"


class TestCooldown:
    def test_run_respects_cooldown(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="cd", handler=lambda: {"summary": "ok"}, cooldown=3600)
        scheduler.register(p)
        scheduler.run_pipeline("cd")
        result = scheduler.run_pipeline("cd")
        assert result.get("status") == "cooldown"


class TestMetrics:
    def test_get_metrics(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="m", handler=lambda: {})
        scheduler.register(p)
        metrics = scheduler.get_metrics()
        assert metrics["pipelines"] >= 1
        assert "stm_size" in metrics
        assert "ltm_count" in metrics
        assert "auto_trigger" in metrics


class TestRunDue:
    def test_run_due_no_pipelines(self, scheduler: UnifiedScheduler) -> None:
        results = scheduler.run_due()
        assert results == []

    def test_run_due_disabled_pipeline(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="off", handler=lambda: {"summary": "done"}, enabled=False)
        scheduler.register(p)
        results = scheduler.run_due()
        assert results == []

    def test_run_due_maintenance_not_due(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="maintenance", handler=lambda: {"summary": "done"}, cooldown=3600)
        scheduler.register(p)
        p.last_run = 9999999999  # far in the future
        results = scheduler.run_due()
        assert len(results) == 0

    def test_run_due_unknown_name_runs(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="custom_check", handler=lambda: {"summary": "custom ok"})
        scheduler.register(p)
        results = scheduler.run_due()
        assert len(results) == 1
        assert results[0]["_status"] == "completed"

    def test_run_due_records_in_ltm(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="custom", handler=lambda: {"summary": "ltm test"})
        scheduler.register(p)
        scheduler.run_due()
        assert scheduler._ltm.count() >= 1


class TestIntegration:
    def test_memory_ltm_after_run(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="integration", handler=lambda: {"summary": "stored"})
        scheduler.register(p)
        scheduler.run_pipeline("integration")
        assert scheduler._ltm.count() == 1

    def test_memory_episodic_after_run(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="ep_test", handler=lambda: {"summary": "ep test"})
        scheduler.register(p)
        scheduler.run_pipeline("ep_test")
        episodes = scheduler._episodic.list_recent(pipeline="ep_test")
        assert len(episodes) == 1
        assert episodes[0].status == "completed"

    def test_memory_semantic_after_run(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="sem_test", handler=lambda: {"summary": "sem test"})
        scheduler.register(p)
        scheduler.run_pipeline("sem_test")
        metrics = scheduler.get_metrics()
        assert metrics["pipelines"] >= 1

    def test_all_memories_integrated(self, scheduler: UnifiedScheduler) -> None:
        p = UnifiedPipeline(name="full_test", handler=lambda: {"summary": "full"})
        scheduler.register(p)
        result = scheduler.run_pipeline("full_test")
        assert result["_status"] == "completed"
        assert scheduler._stm is not None
        assert scheduler._ltm.count() >= 1
        assert len(scheduler._episodic.list_recent()) >= 1
        assert scheduler._trigger.get_stats() is not None
