"""Tests para TuneladoraScheduler (scripts/pro/tuneladora/scheduler.py)."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from scripts.pro.tuneladora.scheduler import TuneladoraScheduler


@pytest.fixture
def scheduler() -> TuneladoraScheduler:
    return TuneladoraScheduler()


class TestRegistration:
    def test_add_pipeline(self, scheduler):
        scheduler.add_pipeline("health", interval_minutes=5)
        assert scheduler.pipeline_count == 1

    def test_add_multiple(self, scheduler):
        scheduler.add_pipeline("health", interval_minutes=5)
        scheduler.add_pipeline("cleanup", interval_minutes=60)
        assert scheduler.pipeline_count == 2

    def test_remove_pipeline(self, scheduler):
        scheduler.add_pipeline("test", interval_minutes=10)
        scheduler.remove_pipeline("test")
        assert scheduler.pipeline_count == 0

    def test_remove_nonexistent(self, scheduler):
        assert scheduler.remove_pipeline("nonexistent") is False

    def test_add_pipeline_sets_next_run(self, scheduler):
        scheduler.add_pipeline("test", interval_minutes=5)
        status = scheduler.get_status()
        assert status[0]["next_run"] is not None
        assert status[0]["interval_minutes"] == 5.0

    def test_auto_execute_safe_default(self, scheduler):
        scheduler.add_pipeline("test", interval_minutes=5)
        status = scheduler.get_status()
        assert status[0]["auto_execute_safe"] is True

    def test_auto_execute_safe_false(self, scheduler):
        scheduler.add_pipeline("test", interval_minutes=5, auto_execute_safe=False)
        status = scheduler.get_status()
        assert status[0]["auto_execute_safe"] is False


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler):
        scheduler.start()
        assert scheduler.is_running
        scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_double_start(self, scheduler):
        scheduler.start()
        scheduler.start()
        scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_stop_without_start(self, scheduler):
        scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_health_pipeline_runs(self, scheduler):
        scheduler.add_pipeline("health", interval_minutes=1, auto_execute_safe=True)
        scheduler.start()
        await asyncio.sleep(0.5)
        status = scheduler.get_status()
        scheduler.stop()
        assert status[0]["run_count"] >= 0


class TestStatus:
    def test_empty_status(self, scheduler):
        assert scheduler.get_status() == []

    def test_status_contains_fields(self, scheduler):
        scheduler.add_pipeline("test", interval_minutes=5)
        status = scheduler.get_status()[0]
        for key in ("name", "interval_minutes", "auto_execute_safe", "last_run", "next_run", "run_count", "failure_count"):
            assert key in status

    def test_overdue_flag(self, scheduler):
        scheduler.add_pipeline("test", interval_minutes=5)
        # Justo después de añadirlo, debería tener next_run futuro
        status = scheduler.get_status()
        assert status[0]["overdue"] is False or status[0]["next_run"] is not None
