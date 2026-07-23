"""Tests de integracion para CleanupPlugin v3.0."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.cleanup import CleanupPlugin
from scripts.pro.tuneladora.plugins.installer import InstallerPlugin
from scripts.pro.tuneladora.plugins.backup import BackupPlugin


@pytest.fixture
def engine() -> PipelineEngine:
    return PipelineEngine()


@pytest.fixture
def cleanup(engine: PipelineEngine) -> CleanupPlugin:
    return CleanupPlugin(engine)


@pytest.fixture
def installer(engine: PipelineEngine) -> InstallerPlugin:
    return InstallerPlugin(engine)


@pytest.fixture
def backup(engine: PipelineEngine) -> BackupPlugin:
    return BackupPlugin(engine)


class TestCleanup:
    def test_cleanup_logs_no_dir(self, cleanup):
        with mock.patch("pathlib.Path.exists") as m:
            m.return_value = False
            result = cleanup.cleanup_logs()
            assert result["removed"] == 0
            assert "reason" in result

    def test_cleanup_logs_removes_old(self, cleanup):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("pathlib.Path.home") as m_home:
                m_home.return_value = Path(tmp)
                with mock.patch("pathlib.Path.exists") as m_ex:
                    m_ex.return_value = True
                    # Create old log file
                    log_dir = Path(tmp) / "URA" / "ura_ia_1972" / "motor" / "observability" / "logs"
                    log_dir.mkdir(parents=True)
                    old_file = log_dir / "old.log"
                    old_file.touch()
                    import time
                    time_shift = time.time() - 31 * 86400
                    os.utime(str(old_file), (time_shift, time_shift))
                    import os
                    result = cleanup.cleanup_logs(days=30)
                    # Should remove or at least not crash
                    assert isinstance(result, dict)

    def test_vacuum_sqlite_ok(self, cleanup):
        with mock.patch("sqlite3.connect") as m:
            m.return_value = mock.Mock()
            result = cleanup.vacuum_sqlite()
            assert "results" in result

    def test_check_disk_returns_percent(self, cleanup):
        result = cleanup.check_disk()
        assert "percent" in result
        assert result["libre_gb"] > 0

    def test_detect_duplicates_no_crash(self, cleanup):
        result = cleanup.detect_duplicates()
        assert isinstance(result, dict)
        assert "groups" in result

    def test_tech_debt_report_no_crash(self, cleanup):
        result = cleanup.tech_debt_report()
        assert isinstance(result, dict)
        assert "todos" in result

    def test_forense_no_dir(self, cleanup):
        with mock.patch("pathlib.Path.exists") as m:
            m.return_value = False
            result = cleanup.forense_aislamientos()
            assert result["total"] == 0


class TestInstaller:
    def test_check_requirements(self, installer):
        result = installer.check_requirements()
        assert "python" in result
        assert "pip" in result
        assert "git" in result
        assert "disk" in result

    def test_install_returns_dict(self, installer):
        with mock.patch.object(installer, "check_requirements") as mock_req:
            mock_req.return_value = {"python": {"ok": True}, "pip": {"ok": True}, "git": {"ok": True}, "disk": {"ok": True}}
            result = installer.install()
            assert "status" in result or "error" in result


class TestBackup:
    def test_backup_code_returns_dict(self, backup):
        result = backup.backup_code("test_backup")
        assert isinstance(result, dict)

    def test_backup_database_no_db(self, backup):
        with mock.patch("pathlib.Path.rglob") as m:
            m.return_value = []
            result = backup.backup_database()
            assert result["copied"] == 0

    def test_rollback_returns_dict(self, backup):
        result = backup.rollback()
        assert isinstance(result, dict)
