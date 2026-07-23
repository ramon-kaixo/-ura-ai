"""Tests de integracion: Scheduler + Brain (A3)."""
from __future__ import annotations

import asyncio
from unittest import mock

import pytest

from motor.brain.auto_maintain import AutoMaintainer
from motor.brain.executor import ProposalExecutor
from motor.brain.observer import BrainObserver


@pytest.fixture
def maintainer() -> AutoMaintainer:
    observer = mock.Mock(spec=BrainObserver)
    executor = mock.Mock(spec=ProposalExecutor)
    return AutoMaintainer(observer, executor)


class TestSchedulerIntegration:
    def test_get_status_without_start(self, maintainer):
        status = maintainer.get_scheduler_status()
        assert status["running"] is False
        assert status["reason"] == "Scheduler not started"

    def test_start_scheduler_adds_pipelines(self, maintainer):
        # Verificar que los pipelines se registran (sin iniciar asyncio)
        try:
            from scripts.pro.tuneladora.scheduler import TuneladoraScheduler
            s = TuneladoraScheduler()
            s.add_pipeline("health", interval_minutes=5, auto_execute_safe=True)
            s.add_pipeline("cleanup", interval_minutes=60, auto_execute_safe=True)
            s.add_pipeline("audit", interval_minutes=360, auto_execute_safe=False)
            assert s.pipeline_count == 3
            status = s.get_status()
            names = [p["name"] for p in status]
            assert "health" in names
            assert "cleanup" in names
            assert "audit" in names
        except ImportError as e:
            pytest.skip(f"Scheduler no disponible: {e}")

    def test_scheduler_add_and_remove_pipeline(self, maintainer):
        try:
            from scripts.pro.tuneladora.scheduler import TuneladoraScheduler
            s = TuneladoraScheduler()
            s.add_pipeline("test", interval_minutes=10)
            assert s.pipeline_count == 1
            s.remove_pipeline("test")
            assert s.pipeline_count == 0
        except ImportError as e:
            pytest.skip(f"Scheduler no disponible: {e}")

    def test_scheduler_pipeline_interval(self, maintainer):
        try:
            from scripts.pro.tuneladora.scheduler import TuneladoraScheduler
            s = TuneladoraScheduler()
            s.add_pipeline("p1", interval_minutes=60, auto_execute_safe=False)
            s.add_pipeline("p2", interval_minutes=5, auto_execute_safe=True)
            status = s.get_status()
            for p in status:
                if p["name"] == "p1":
                    assert p["interval_minutes"] == 60.0
                    assert p["auto_execute_safe"] is False
                if p["name"] == "p2":
                    assert p["interval_minutes"] == 5.0
                    assert p["auto_execute_safe"] is True
        except ImportError as e:
            pytest.skip(f"Scheduler no disponible: {e}")

    def test_scheduler_start_needs_loop(self, maintainer):
        """Verificar que start() requiere event loop (comportamiento esperado)."""
        try:
            from scripts.pro.tuneladora.scheduler import TuneladoraScheduler
            s = TuneladoraScheduler()
            s.add_pipeline("test", interval_minutes=5)
            with pytest.raises(RuntimeError, match="no running event loop"):
                s.start()
        except ImportError as e:
            pytest.skip(f"Scheduler no disponible: {e}")


@mock.patch("subprocess.run")
class TestAutoFixCode:
    def test_auto_fix_code_runs_ruff(self, mock_run, maintainer):
        mock_run.return_value = mock.Mock(returncode=0, stdout="fixed 1 error", stderr="")
        result = maintainer.auto_fix_code("motor/brain/")
        assert "fix_log" in result
        assert mock_run.called

    def test_auto_fix_code_no_changes(self, mock_run, maintainer):
        # Simula: ruff fix ok, ruff format ok, git diff clean
        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if "diff" in cmd_str:
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="OK", stderr="")
        mock_run.side_effect = side_effect
        result = maintainer.auto_fix_code("motor/brain/")
        assert result["status"] == "no_changes"

    def test_auto_fix_code_commits_changes(self, mock_run, maintainer):
        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if "diff" in cmd_str:
                return mock.Mock(returncode=1, stdout=" M test.py", stderr="")
            return mock.Mock(returncode=0, stdout="OK", stderr="")
        mock_run.side_effect = side_effect
        result = maintainer.auto_fix_code("motor/brain/")
        assert result["status"] == "committed"

    def test_auto_fix_code_risk_safe(self, maintainer):
        from motor.brain.auto_maintain import MaintenanceProposal
        from motor.brain.alerts import Alert

        alert = Alert(severity="info", title="code quality", description="", affected_subsystems=["code"], timestamp=123.0)
        proposal = MaintenanceProposal(alert=alert, action="auto_fix_code", target="motor/brain/", params={})
        risk = AutoMaintainer._classify_risk(proposal)
        assert risk == "safe"

    def test_auto_fix_code_action_type(self, maintainer):
        """auto_fix_code se mapea a tipo 'format'."""
        from motor.brain.auto_maintain import MaintenanceProposal
        action = AutoMaintainer._action_to_type("auto_fix_code")
        assert action == "format"
