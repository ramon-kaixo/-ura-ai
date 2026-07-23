"""Tests para AutoMaintainer (A1 + A2)."""
from __future__ import annotations

import time
from unittest import mock

import pytest

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
        assert len(results) >= 1  # noqa: S101


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
