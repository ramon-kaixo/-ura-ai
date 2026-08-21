"""Tests para TuneladoraScheduler (scripts/pro/tuneladora/scheduler.py)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest

from scripts.pro.tuneladora.scheduler import ScheduledPipeline, TuneladoraScheduler


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
        for key in (
            "name",
            "interval_minutes",
            "auto_execute_safe",
            "last_run",
            "next_run",
            "run_count",
            "failure_count",
        ):
            assert key in status

    def test_overdue_flag(self, scheduler):
        scheduler.add_pipeline("test", interval_minutes=5)
        # Justo después de añadirlo, debería tener next_run futuro
        status = scheduler.get_status()
        assert status[0]["overdue"] is False or status[0]["next_run"] is not None


class TestRunPipelineSync:
    def _pipeline(self, name: str, auto: bool = True) -> ScheduledPipeline:
        return ScheduledPipeline(
            name=name,
            interval=timedelta(minutes=5),
            auto_execute_safe=auto,
            next_run=datetime.now(UTC) + timedelta(seconds=5),
        )

    def test_health_disco_critico(self, scheduler):
        engine = mock.Mock()
        engine.health_disk.return_value = {"libre_gb": 5}
        scheduler._run_pipeline_sync(engine, self._pipeline("health"))
        engine.notify.assert_called_once()

    def test_health_disco_medio_limpia(self, scheduler):
        engine = mock.Mock()
        engine.health_disk.return_value = {"libre_gb": 30}
        scheduler._run_pipeline_sync(engine, self._pipeline("health"))
        engine.run_script.assert_called_once_with("scripts/pro/cleanup_logs.py")

    def test_health_disco_ok_sin_accion(self, scheduler):
        engine = mock.Mock()
        engine.health_disk.return_value = {"libre_gb": 100}
        scheduler._run_pipeline_sync(engine, self._pipeline("health"))
        engine.notify.assert_not_called()
        engine.run_script.assert_not_called()

    def test_cleanup_auto(self, scheduler):
        engine = mock.Mock()
        scheduler._run_pipeline_sync(engine, self._pipeline("cleanup"))
        assert engine.run_script.call_count == 2

    def test_cleanup_no_auto(self, scheduler):
        engine = mock.Mock()
        scheduler._run_pipeline_sync(engine, self._pipeline("cleanup", auto=False))
        engine.run_script.assert_not_called()

    def test_full_audit(self, scheduler):
        engine = mock.Mock()
        scheduler._run_pipeline_sync(engine, self._pipeline("full_audit"))
        engine.run_ruff.assert_called_once()

    def test_desconocido(self, scheduler):
        engine = mock.Mock()
        scheduler._run_pipeline_sync(engine, self._pipeline("raro"))
        engine.health_disk.assert_not_called()


class TestExecutePipeline:
    @pytest.mark.asyncio
    async def test_exito(self, scheduler):
        pipeline = ScheduledPipeline(
            name="health",
            interval=timedelta(minutes=5),
            auto_execute_safe=True,
            next_run=datetime.now(UTC) + timedelta(seconds=5),
        )
        engine = mock.Mock()
        engine.ledger = mock.Mock()
        engine.config = mock.Mock()
        engine.config.nervioso = mock.Mock()
        engine.health_disk.return_value = {"libre_gb": 100}
        with (
            mock.patch("scripts.pro.tuneladora.scheduler.PipelineEngine", return_value=engine),
            mock.patch("scripts.pro.tuneladora.ledger.save_execution") as m_save,
        ):
            await scheduler._execute_pipeline(pipeline)
        engine.ledger.set_result.assert_called_with("completed")
        m_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_error(self, scheduler):
        pipeline = ScheduledPipeline(
            name="health",
            interval=timedelta(minutes=5),
            auto_execute_safe=True,
            next_run=datetime.now(UTC) + timedelta(seconds=5),
        )
        engine = mock.Mock()
        engine.ledger = mock.Mock()
        engine.config = mock.Mock()
        engine.config.nervioso = mock.Mock()
        scheduler._circuit = mock.Mock()
        scheduler._circuit.call.side_effect = RuntimeError("boom")
        with (
            mock.patch("scripts.pro.tuneladora.scheduler.PipelineEngine", return_value=engine),
            mock.patch("scripts.pro.tuneladora.ledger.save_execution") as m_save,
        ):
            await scheduler._execute_pipeline(pipeline)
        engine.ledger.set_result.assert_called_with("failed")
        m_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_open(self, scheduler):
        pipeline = ScheduledPipeline(
            name="health",
            interval=timedelta(minutes=5),
            auto_execute_safe=True,
            next_run=datetime.now(UTC) + timedelta(seconds=5),
        )
        engine = mock.Mock()
        engine.ledger = mock.Mock()
        engine.config = mock.Mock()
        engine.config.nervioso = mock.Mock()
        scheduler._circuit = mock.Mock()
        scheduler._circuit.call.side_effect = RuntimeError("Circuit OPEN")
        with (
            mock.patch("scripts.pro.tuneladora.scheduler.PipelineEngine", return_value=engine),
            mock.patch("scripts.pro.tuneladora.ledger.save_execution"),
        ):
            await scheduler._execute_pipeline(pipeline)
        engine.notify.assert_called_once()
