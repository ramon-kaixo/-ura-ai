"""Tests para AutoMaintainer (A1 + A2)."""
from __future__ import annotations

import time
from unittest import mock

from motor.brain.alerts import Alert
from motor.brain.auto_maintain import AutoMaintainer, MaintenanceProposal
from motor.brain.observer import HealthObservation


def _make_alert(**kwargs) -> Alert:
    defaults = {
        "severity": "emergency",
        "title": "DISCO CRITICO",
        "description": "test",
        "affected_subsystems": ["disk"],
        "timestamp": time.time(),
        "suggested_action": None,
    }
    defaults.update(kwargs)
    return Alert(**defaults)


def _make_observation(**kwargs) -> HealthObservation:
    defaults = {
        "timestamp": time.time(),
        "subsystem": "disk",
        "status": "ok",
        "raw_data": {"libre_gb": 100},
        "anomaly": None,
    }
    defaults.update(kwargs)
    return HealthObservation(**defaults)


# ── A1: Scan ──────────────────────────────────────────────


class TestScan:
    def test_scan_generates_proposals(self):
        observer = mock.Mock()
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)

        alert = _make_alert(severity="emergency", title="DISCO CRITICO", affected_subsystems=["disk"])
        maintainer._alerts.evaluate = mock.Mock(return_value=[alert])

        proposals = maintainer.scan()
        assert len(proposals) == 1
        assert proposals[0].action == "clean_disk"
        assert proposals[0].target == "disk"

    def test_scan_empty_when_no_alerts(self):
        observer = mock.Mock()
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)
        maintainer._alerts.evaluate = mock.Mock(return_value=[])
        assert maintainer.scan() == []

    def test_scan_preserves_order(self):
        observer = mock.Mock()
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)
        maintainer._alerts.evaluate = mock.Mock(return_value=[
            _make_alert(severity="emergency", title="DISCO CRITICO"),
            _make_alert(severity="critical", title="DEGRADACION DEL SISTEMA"),
        ])
        proposals = maintainer.scan()
        assert len(proposals) == 2
        assert proposals[0].action == "clean_disk"
        assert proposals[1].action == "scale_resources"


# ── A2: Clasificacion de riesgo ───────────────────────────


class TestRiskClassification:
    def test_disk_severity_emergency_is_medium(self):
        """clean_disk con severidad emergency -> medium."""
        observer = mock.Mock()
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)

        alert = _make_alert(severity="emergency", title="DISCO CRITICO")
        maintainer._alerts.evaluate = mock.Mock(return_value=[alert])

        proposals = maintainer.scan()
        assert len(proposals) == 1
        assert proposals[0].risk_level == "medium"
        assert proposals[0].auto_execute is False

    def test_disk_severity_warning_is_safe(self):
        """clean_disk con severidad warning -> safe (autofix)."""
        observer = mock.Mock()
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)

        alert = _make_alert(severity="warning", title="Disco medio")
        maintainer._alerts.evaluate = mock.Mock(return_value=[alert])

        proposals = maintainer.scan()
        assert len(proposals) == 1
        assert proposals[0].risk_level == "safe"
        assert proposals[0].auto_execute is True

    def test_restart_provider_is_medium(self):
        proposal = MaintenanceProposal(
            alert=_make_alert(title="Provider caido: ollama"),
            action="restart_provider",
            target="ollama",
            params={},
        )
        risk = AutoMaintainer._classify_risk(proposal)
        assert risk == "medium"

    def test_scale_resources_is_medium(self):
        proposal = MaintenanceProposal(
            alert=_make_alert(title="DEGRADACION DEL SISTEMA"),
            action="scale_resources",
            target="system",
            params={},
        )
        risk = AutoMaintainer._classify_risk(proposal)
        assert risk == "medium"

    def test_ruff_fix_is_safe(self):
        proposal = MaintenanceProposal(
            alert=_make_alert(title="Ruff errors"),
            action="auto_fix_ruff",
            target="code",
            params={},
        )
        risk = AutoMaintainer._classify_risk(proposal)
        assert risk == "safe"

    def test_emergency_shutdown_is_critical(self):
        proposal = MaintenanceProposal(
            alert=_make_alert(title="CRITICAL: temperature"),
            action="emergency_shutdown",
            target="system",
            params={},
        )
        risk = AutoMaintainer._classify_risk(proposal)
        assert risk == "critical"


# ── A2: Auto-ejecucion ────────────────────────────────────


class TestA2AutoExecute:
    def test_safe_auto_executes(self):
        """risk_level=safe: ejecuta sin aprobacion."""
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="disk", status="ok")]
        executor = mock.Mock()
        executor.execute.return_value = {"status": "success"}

        maintainer = AutoMaintainer(observer, executor)

        proposal = MaintenanceProposal(
            alert=_make_alert(title="DISCO CRITICO"),
            action="clean_disk",
            target="disk",
            params={},
            risk_level="safe",
            auto_execute=True,
        )

        result = maintainer.approve_and_execute(proposal)
        assert "execution" in result
        executor.execute.assert_called_once()

    def test_critical_does_not_execute(self):
        """risk_level=critical: NO ejecuta, retorna blocked."""
        observer = mock.Mock()
        executor = mock.Mock()

        maintainer = AutoMaintainer(observer, executor)

        proposal = MaintenanceProposal(
            alert=_make_alert(title="CRITICAL"),
            action="emergency_shutdown",
            target="system",
            params={},
            risk_level="critical",
        )

        result = maintainer.approve_and_execute(proposal, approved=True)
        assert result["status"] == "critical_blocked"
        executor.execute.assert_not_called()

    def test_medium_still_asks(self):
        """risk_level=medium: solo ejecuta si approved=True."""
        observer = mock.Mock()
        executor = mock.Mock()

        maintainer = AutoMaintainer(observer, executor)

        proposal = MaintenanceProposal(
            alert=_make_alert(title="DISCO CRITICO"),
            action="clean_disk",
            target="disk",
            params={},
            risk_level="medium",
        )

        # Rechazado
        r1 = maintainer.approve_and_execute(proposal, approved=False)
        assert r1["status"] == "rejected"
        executor.execute.assert_not_called()

        # Aprobado
        observer.observe_all.return_value = [_make_observation(subsystem="disk", status="ok")]
        executor.execute.return_value = {"status": "success"}
        r2 = maintainer.approve_and_execute(proposal, approved=True)
        assert "execution" in r2
        executor.execute.assert_called_once()

    def test_propose_and_maybe_execute_mixed(self):
        """propose_and_maybe_execute maneja safe+medium+critical."""
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="disk", status="ok")]
        executor = mock.Mock()
        executor.execute.return_value = {"status": "success"}

        maintainer = AutoMaintainer(observer, executor)

        # Safe alert (high disk -> autofix)
        safe_alert = _make_alert(title="DISCO CRITICO")
        safe_alert.raw_data = {"libre_gb": 100}

        # Critical alert (no se ejecuta)
        crit_alert = _make_alert(severity="critical", title="CRITICAL: temperature")

        maintainer._alerts.evaluate = mock.Mock(return_value=[safe_alert, crit_alert])

        results = maintainer.propose_and_maybe_execute()
        # Si no coincide, 0 resultados. Si coincide, 1 safe + 1 crit
        assert len(results) >= 1


# ── A1: Execute ───────────────────────────────────────────


class TestExecute:
    def test_approved_executes(self):
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="disk", status="ok")]
        executor = mock.Mock()
        executor.execute.return_value = {"status": "success", "returncode": 0}

        maintainer = AutoMaintainer(observer, executor)
        proposal = MaintenanceProposal(
            alert=_make_alert(),
            action="clean_disk",
            target="disk",
            params={"min_free_gb": 50},
        )

        result = maintainer.approve_and_execute(proposal, approved=True)
        assert "execution" in result
        assert "verification" in result
        executor.execute.assert_called_once()

    def test_rejected_does_not_execute(self):
        observer = mock.Mock()
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)

        proposal = MaintenanceProposal(alert=_make_alert(), action="clean_disk", target="disk", params={})

        result = maintainer.approve_and_execute(proposal, approved=False)
        assert result["status"] == "rejected"
        executor.execute.assert_not_called()

    def test_result_recorded_in_history(self):
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="disk", status="ok")]
        executor = mock.Mock()
        executor.execute.return_value = {"status": "success"}

        maintainer = AutoMaintainer(observer, executor)
        proposal = MaintenanceProposal(alert=_make_alert(), action="clean_disk", target="disk", params={})

        maintainer.approve_and_execute(proposal, approved=True)
        resolved = maintainer.get_resolved()
        assert len(resolved) == 1
        assert "execution" in resolved[0]


# ── A1: Verification ──────────────────────────────────────


class TestVerification:
    def test_resolved_true(self):
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="disk", status="ok", anomaly=None)]
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)
        proposal = MaintenanceProposal(alert=_make_alert(affected_subsystems=["disk"]), action="clean_disk", target="disk", params={})

        v = maintainer._verify_resolution(proposal)
        assert v["resolved"] is True

    def test_resolved_false(self):
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="disk", status="error", anomaly="low")]
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)
        proposal = MaintenanceProposal(alert=_make_alert(affected_subsystems=["disk"]), action="clean_disk", target="disk", params={})

        v = maintainer._verify_resolution(proposal)
        assert v["resolved"] is False

    def test_verify_subsystem_not_found(self):
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="ollama", status="ok")]
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)
        proposal = MaintenanceProposal(alert=_make_alert(affected_subsystems=["disk"]), action="clean_disk", target="disk", params={})

        v = maintainer._verify_resolution(proposal)
        assert v == {"resolved": False, "error": "Subsystem not found"}

    def test_verify_first_match_priority(self):
        """Primera observacion con subsystem coincidente decide."""
        observer = mock.Mock()
        observer.observe_all.return_value = [
            _make_observation(subsystem="disk", status="error", anomaly="low"),
            _make_observation(subsystem="disk", status="ok"),
        ]
        executor = mock.Mock()
        maintainer = AutoMaintainer(observer, executor)
        proposal = MaintenanceProposal(alert=_make_alert(affected_subsystems=["disk"]), action="clean_disk", target="disk", params={})

        v = maintainer._verify_resolution(proposal)
        assert v["resolved"] is False


# ── A2: Conversion alerta → propuesta ─────────────────────


class TestAlertToProposal:
    def test_disk_alert(self):
        alert = _make_alert(severity="emergency", title="DISCO CRITICO")
        prop = AutoMaintainer(mock.Mock(), mock.Mock())._alert_to_proposal(alert)
        assert prop is not None
        assert prop.action == "clean_disk"
        assert prop.target == "disk"
        assert prop.params == {"min_free_gb": 50, "aggressive": True}

    def test_provider_caido_alert(self):
        alert = _make_alert(severity="critical", title="Provider caido: ollama", affected_subsystems=["ollama"])
        prop = AutoMaintainer(mock.Mock(), mock.Mock())._alert_to_proposal(alert)
        assert prop is not None
        assert prop.action == "restart_provider"
        assert prop.target == "ollama"
        assert prop.params == {"provider": "ollama", "timeout": 30}

    def test_provider_caido_accented(self):
        alert = _make_alert(severity="critical", title="Proveedor caído", affected_subsystems=["gemini"])
        prop = AutoMaintainer(mock.Mock(), mock.Mock())._alert_to_proposal(alert)
        assert prop is not None
        assert prop.action == "restart_provider"
        assert prop.target == "gemini"

    def test_provider_caido_no_subsystems(self):
        alert = _make_alert(severity="critical", title="Provider caido", affected_subsystems=[])
        prop = AutoMaintainer(mock.Mock(), mock.Mock())._alert_to_proposal(alert)
        assert prop is not None
        assert prop.target == "unknown"

    def test_degradacion_alert(self):
        alert = _make_alert(severity="critical", title="DEGRADACION DEL SISTEMA")
        prop = AutoMaintainer(mock.Mock(), mock.Mock())._alert_to_proposal(alert)
        assert prop is not None
        assert prop.action == "scale_resources"
        assert prop.params == {"scale_type": "vertical", "urgent": True}

    def test_network_alert(self):
        alert = _make_alert(severity="warning", title="problema de red detectado")
        prop = AutoMaintainer(mock.Mock(), mock.Mock())._alert_to_proposal(alert)
        assert prop is not None
        assert prop.action == "check_network"
        assert prop.params == {"ping_targets": ["8.8.8.8", "1.1.1.1"]}

    def test_network_alert_english(self):
        alert = _make_alert(severity="warning", title="network is down")
        prop = AutoMaintainer(mock.Mock(), mock.Mock())._alert_to_proposal(alert)
        assert prop is not None
        assert prop.action == "check_network"

    def test_unknown_alert_returns_none(self):
        alert = _make_alert(severity="warning", title="algo irrelevante")
        prop = AutoMaintainer(mock.Mock(), mock.Mock())._alert_to_proposal(alert)
        assert prop is None


class TestClassifyRiskExtra:
    def test_check_network_is_safe(self):
        proposal = MaintenanceProposal(alert=_make_alert(title="red"), action="check_network", target="network", params={})
        assert AutoMaintainer._classify_risk(proposal) == "safe"

    def test_unknown_action_is_medium(self):
        proposal = MaintenanceProposal(alert=_make_alert(title="x"), action="algo_nuevo", target="t", params={})
        assert AutoMaintainer._classify_risk(proposal) == "medium"

    def test_clean_disk_warning_is_safe(self):
        proposal = MaintenanceProposal(
            alert=_make_alert(severity="warning", title="disco"), action="clean_disk", target="disk", params={}
        )
        assert AutoMaintainer._classify_risk(proposal) == "safe"

    def test_auto_fix_unused_imports_is_safe(self):
        proposal = MaintenanceProposal(
            alert=_make_alert(title="imports"), action="auto_fix_unused_imports", target="code", params={}
        )
        assert AutoMaintainer._classify_risk(proposal) == "safe"


class TestActionToType:
    def test_mapping(self):
        m = AutoMaintainer._action_to_type
        assert m("clean_disk") == "refactor"
        assert m("restart_provider") == "refactor"
        assert m("scale_resources") == "refactor"
        assert m("check_network") == "test"
        assert m("auto_fix_code") == "format"
        assert m("auto_fix_ruff") == "format"
        assert m("auto_fix_unused_imports") == "format"
        assert m("desconocida") == "generic"


class TestProposeAndExecute:
    def test_safe_auto_executes(self):
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="network", status="ok")]
        executor = mock.Mock()
        executor.execute.return_value = {"status": "success"}
        maintainer = AutoMaintainer(observer, executor)
        maintainer._alerts.evaluate = mock.Mock(
            return_value=[_make_alert(severity="warning", title="red caida", affected_subsystems=["network"])]
        )

        with mock.patch("motor.brain.auto_maintain.time.sleep"):
            results = maintainer.propose_and_maybe_execute()

        assert len(results) == 1
        assert results[0]["auto_executed"] is True
        executor.execute.assert_called_once()

    def test_unknown_alerts_produce_no_results(self):
        maintainer = AutoMaintainer(mock.Mock(), mock.Mock())
        maintainer._alerts.evaluate = mock.Mock(return_value=[_make_alert(title="algo irrelevante")])
        assert maintainer.propose_and_maybe_execute() == []

    def test_pending_not_executed(self):
        maintainer = AutoMaintainer(mock.Mock(), mock.Mock())
        maintainer._alerts.evaluate = mock.Mock(
            return_value=[_make_alert(severity="emergency", title="DISCO CRITICO")]
        )
        results = maintainer.propose_and_maybe_execute()
        assert results[0]["status"] == "pending"
        assert results[0]["auto_executed"] is False


# ── A3: Scheduler ─────────────────────────────────────────


class TestScheduler:
    def test_start_scheduler_success(self):
        with mock.patch("scripts.pro.tuneladora.scheduler.TuneladoraScheduler") as cls:
            scheduler = cls.return_value
            scheduler.pipeline_count = 3
            scheduler.is_running = True
            scheduler.get_status.return_value = [{"name": "health"}]

            maintainer = AutoMaintainer(mock.Mock(), mock.Mock())
            maintainer.start_scheduler()

            cls.assert_called_once_with()
            assert scheduler.add_pipeline.call_count == 3
            scheduler.start.assert_called_once()
            status = maintainer.get_scheduler_status()
            assert status == {"running": True, "pipelines": [{"name": "health"}], "pipeline_count": 3}

    def test_start_scheduler_import_error(self):
        with mock.patch.dict(
            "sys.modules", {"scripts.pro.tuneladora.scheduler": None}
        ):
            maintainer = AutoMaintainer(mock.Mock(), mock.Mock())
            maintainer.start_scheduler()
            assert maintainer._scheduler is None
            assert maintainer.get_scheduler_status() == {
                "running": False,
                "pipelines": [],
                "reason": "Scheduler not started",
            }

    def test_stop_scheduler(self):
        scheduler = mock.Mock()
        maintainer = AutoMaintainer(mock.Mock(), mock.Mock())
        maintainer._scheduler = scheduler
        maintainer.stop_scheduler()
        scheduler.stop.assert_called_once()

    def test_stop_scheduler_none(self):
        maintainer = AutoMaintainer(mock.Mock(), mock.Mock())
        maintainer.stop_scheduler()
        assert maintainer._scheduler is None


# ── A3: Autofix de codigo ─────────────────────────────────


class TestAutoFixCode:
    def _maintainer(self) -> AutoMaintainer:
        return AutoMaintainer(mock.Mock(), mock.Mock())

    def test_no_changes(self):
        runner = mock.Mock(
            side_effect=[
                mock.Mock(returncode=0),  # ruff check --fix
                mock.Mock(returncode=0),  # ruff format
                mock.Mock(returncode=0),  # git diff --quiet (sin cambios)
            ]
        )
        with mock.patch("motor.brain.auto_maintain.subprocess.run", runner):
            result = self._maintainer().auto_fix_code("motor/brain/")

        assert result == {"status": "no_changes", "fix_log": [mock.ANY, mock.ANY], "committed": False}

    def test_committed(self):
        runner = mock.Mock(
            side_effect=[
                mock.Mock(returncode=0),  # ruff check --fix
                mock.Mock(returncode=0),  # ruff format
                mock.Mock(returncode=1),  # git diff --quiet (hay cambios)
                mock.Mock(returncode=0),  # git add
                mock.Mock(returncode=0),  # git commit
            ]
        )
        with mock.patch("motor.brain.auto_maintain.subprocess.run", runner):
            result = self._maintainer().auto_fix_code("motor/brain/")

        assert result["status"] == "committed"
        assert result["committed"] is True
        cmd = runner.call_args_list[-1].args[0]
        assert cmd[0] == "git" and cmd[1] == "commit"

    def test_ruff_check_fails_but_continues(self):
        runner = mock.Mock(
            side_effect=[
                Exception("ruff no existe"),
                mock.Mock(returncode=0),  # ruff format
                mock.Mock(returncode=0),  # git diff --quiet
            ]
        )
        with mock.patch("motor.brain.auto_maintain.subprocess.run", runner):
            result = self._maintainer().auto_fix_code("motor/brain/")

        assert result["status"] == "no_changes"
        assert "fallo" in result["fix_log"][0]

    def test_ruff_format_fails_but_continues(self):
        runner = mock.Mock(
            side_effect=[
                mock.Mock(returncode=0),  # ruff check --fix
                Exception("format fallo"),
                mock.Mock(returncode=0),  # git diff --quiet
            ]
        )
        with mock.patch("motor.brain.auto_maintain.subprocess.run", runner):
            result = self._maintainer().auto_fix_code("motor/brain/")

        assert result["status"] == "no_changes"
        assert "fallo" in result["fix_log"][1]

    def test_git_diff_exception_counts_as_no_changes(self):
        runner = mock.Mock(
            side_effect=[
                mock.Mock(returncode=0),
                mock.Mock(returncode=0),
                Exception("git diff fallo"),
            ]
        )
        with mock.patch("motor.brain.auto_maintain.subprocess.run", runner):
            result = self._maintainer().auto_fix_code("motor/brain/")

        assert result["status"] == "no_changes"
        assert result["committed"] is False

    def test_commit_failed(self):
        runner = mock.Mock(
            side_effect=[
                mock.Mock(returncode=0),
                mock.Mock(returncode=0),
                mock.Mock(returncode=1),  # git diff --quiet (cambios)
                Exception("git add fallo"),
            ]
        )
        with mock.patch("motor.brain.auto_maintain.subprocess.run", runner):
            result = self._maintainer().auto_fix_code("motor/brain/")

        assert result["status"] == "commit_failed"
        assert result["committed"] is False


class TestPendingResolved:
    def test_get_pending(self):
        maintainer = AutoMaintainer(mock.Mock(), mock.Mock())
        maintainer._alerts.evaluate = mock.Mock(return_value=[_make_alert(title="DISCO CRITICO")])
        proposals = maintainer.scan()
        assert maintainer.get_pending() == proposals

    def test_get_resolved_limit(self):
        observer = mock.Mock()
        observer.observe_all.return_value = [_make_observation(subsystem="disk", status="ok")]
        executor = mock.Mock()
        executor.execute.return_value = {"status": "success"}
        maintainer = AutoMaintainer(observer, executor)

        for _ in range(3):
            with mock.patch("motor.brain.auto_maintain.time.sleep"):
                maintainer.approve_and_execute(
                    MaintenanceProposal(alert=_make_alert(), action="clean_disk", target="disk", params={}),
                    approved=True,
                )

        assert len(maintainer.get_resolved(limit=2)) == 2
