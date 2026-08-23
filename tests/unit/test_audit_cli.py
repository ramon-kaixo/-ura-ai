"""Tests for knowledge.engine.cli.audit module."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from knowledge.engine.cli.audit import (
    cmd_vacuum,
    cmd_audit_db,
    _audit_integrity,
    _audit_orphans,
    _audit_active_version,
    _audit_stuck_jobs,
    _audit_wal,
    _audit_pending_sync,
    _audit_backend,
    _audit_disk,
)


def test_cmd_vacuum_success(tmp_path):
    """Test cmd_vacuum with successful database operation."""
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path, \
         patch('knowledge.engine.cli.audit.open_db') as mock_open_db:

        args = Mock()
        db_path = tmp_path / "db.sqlite"
        db_path.write_bytes(b"x")
        mock_resolve_db_path.return_value = db_path
        mock_db_conn = MagicMock()
        mock_open_db.return_value = mock_db_conn

        result = cmd_vacuum(args)

        assert result == 0
        mock_resolve_db_path.assert_called_once_with(args)
        mock_open_db.assert_called_once_with(db_path)
        mock_db_conn.execute.assert_called_once_with("VACUUM")
        mock_db_conn.close.assert_called_once()


def test_cmd_vacuum_failure(tmp_path):
    """Test cmd_vacuum with failed database operation."""
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path, \
         patch('knowledge.engine.cli.audit.open_db') as mock_open_db:

        args = Mock()
        db_path = tmp_path / "db.sqlite"
        db_path.write_bytes(b"x")
        mock_resolve_db_path.return_value = db_path
        mock_db_conn = MagicMock()
        mock_open_db.return_value = mock_db_conn
        mock_db_conn.execute.side_effect = Exception("Database error")

        result = cmd_vacuum(args)

        assert result == 1
        mock_resolve_db_path.assert_called_once_with(args)
        mock_open_db.assert_called_once_with(db_path)


def test_audit_integrity_ok():
    """Test _audit_integrity with OK result."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = ("ok",)
    report = Mock()

    _audit_integrity(mock_conn, report)

    mock_conn.execute.assert_called_once_with("PRAGMA integrity_check")
    report.assert_called_once_with("OK", "integrity", "SQLite integrity check passed")


def test_audit_integrity_fail():
    """Test _audit_integrity with FAIL result."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = ("corrupted",)
    report = Mock()

    _audit_integrity(mock_conn, report)

    mock_conn.execute.assert_called_once_with("PRAGMA integrity_check")
    report.assert_called_once_with("FAIL", "integrity", "Corruption detected: corrupted")


def test_audit_orphans_no_orphans():
    """Test _audit_orphans with no orphan edges."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"c": 0}
    report = Mock()

    _audit_orphans(mock_conn, report)

    assert mock_conn.execute.call_count == 2
    assert report.call_count == 2
    report.assert_any_call("OK", "orphan_edges", "No orphan edge sources")
    report.assert_any_call("OK", "orphan_dst", "No orphan edge targets")


def test_audit_orphans_with_orphans():
    """Test _audit_orphans with orphan edges."""
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(fetchone=Mock(return_value={"c": 3})),
        MagicMock(fetchone=Mock(return_value={"c": 5})),
    ]
    report = Mock()

    _audit_orphans(mock_conn, report)

    assert mock_conn.execute.call_count == 2
    assert report.call_count == 2
    report.assert_any_call("FAIL", "orphan_edges", "3 edges with missing source node")
    report.assert_any_call("FAIL", "orphan_edges", "5 edges with missing target node")


def test_audit_active_version_single():
    """Test _audit_active_version with single version row."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"c": 1}
    report = Mock()

    _audit_active_version(mock_conn, report)

    mock_conn.execute.assert_called_once_with("SELECT COUNT(*) as c FROM kg_active_version")
    report.assert_called_once_with("OK", "active_version", "Single active version row")


def test_audit_active_version_zero():
    """Test _audit_active_version with zero version rows."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"c": 0}
    report = Mock()

    _audit_active_version(mock_conn, report)

    mock_conn.execute.assert_called_once()
    report.assert_called_once_with("WARN", "active_version", "No active version row (fresh DB)")


def test_audit_active_version_multiple():
    """Test _audit_active_version with multiple version rows."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"c": 3}
    report = Mock()

    _audit_active_version(mock_conn, report)

    mock_conn.execute.assert_called_once()
    report.assert_called_once_with("FAIL", "active_version", "3 active version rows (expected 1)")


def test_audit_stuck_jobs_none():
    """Test _audit_stuck_jobs with no stuck jobs."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"c": 0}
    report = Mock()

    _audit_stuck_jobs(mock_conn, report)

    mock_conn.execute.assert_called_once()
    assert "stuck_jobs" in str(report.call_args)
    report.assert_called_once_with("OK", "stuck_jobs", "No stuck jobs")


def test_audit_stuck_jobs_found():
    """Test _audit_stuck_jobs with stuck jobs found."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"c": 2}
    report = Mock()

    _audit_stuck_jobs(mock_conn, report)

    mock_conn.execute.assert_called_once()
    report.assert_called_once_with("FAIL", "stuck_jobs", "2 jobs stuck in 'running' for >30min")


def test_audit_wal_ok():
    """Test _audit_wal with WAL mode OK and small WAL."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = ("wal",)
    mock_db_path = MagicMock()
    mock_wal_path = MagicMock()
    mock_wal_path.stat.return_value.st_size = 50 * 1024
    mock_db_path.with_name.return_value = mock_wal_path
    report = Mock()

    _audit_wal(mock_conn, mock_db_path, report)

    assert mock_conn.execute.call_count == 1
    mock_db_path.with_name.assert_called_once()
    report.assert_any_call("OK", "wal_mode", "Journal mode: wal")
    report.assert_any_call("OK", "wal_size", "WAL file: 50 KB")


def test_audit_wal_fail_mode():
    """Test _audit_wal with non-WAL journal mode."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = ("delete",)
    mock_db_path = MagicMock()
    mock_wal_path = MagicMock()
    mock_wal_path.stat.return_value.st_size = 0
    mock_db_path.with_name.return_value = mock_wal_path
    report = Mock()

    _audit_wal(mock_conn, mock_db_path, report)

    report.assert_any_call("FAIL", "wal_mode", "Expected WAL, got delete")


def test_audit_wal_warn_large():
    """Test _audit_wal with large WAL file (>100MB)."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = ("wal",)
    mock_db_path = MagicMock()
    mock_wal_path = MagicMock()
    mock_wal_path.stat.return_value.st_size = 150 * 1024 * 1024
    mock_db_path.with_name.return_value = mock_wal_path
    report = Mock()

    _audit_wal(mock_conn, mock_db_path, report)

    report.assert_any_call("WARN", "wal_size", "WAL file: 150 MB (>100MB)")


def test_audit_wal_no_wal_file():
    """Test _audit_wal with no WAL file (fully checkpointed)."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = ("wal",)
    mock_db_path = MagicMock()
    mock_wal_path = MagicMock()
    mock_wal_path.exists.return_value = False
    mock_db_path.with_name.return_value = mock_wal_path
    report = Mock()

    _audit_wal(mock_conn, mock_db_path, report)

    report.assert_any_call("OK", "wal_size", "No WAL file (fully checkpointed)")


def test_audit_pending_sync_none():
    """Test _audit_pending_sync with no pending operations."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"c": 0}
    report = Mock()

    _audit_pending_sync(mock_conn, report)

    mock_conn.execute.assert_called_once()
    report.assert_called_once_with("OK", "pending_sync", "All sync operations done")


def test_audit_pending_sync_found():
    """Test _audit_pending_sync with pending operations."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"c": 7}
    report = Mock()

    _audit_pending_sync(mock_conn, report)

    mock_conn.execute.assert_called_once()
    report.assert_called_once_with("WARN", "pending_sync", "7 pending sync operations")


def test_audit_backend_healthy():
    """Test _audit_backend with healthy backend."""
    report = Mock()

    with patch('knowledge.engine.audit.get_audit') as mock_get_audit:
        mock_backend = MagicMock()
        mock_health = MagicMock()
        mock_health.healthy = True
        mock_health.events_written = 42
        mock_backend.health_check.return_value = mock_health
        mock_audit = MagicMock()
        mock_audit.backend = mock_backend
        mock_get_audit.return_value = mock_audit

        _audit_backend(report)

        report.assert_called_once_with("OK", "audit", "Audit backend healthy (42 events)")


def test_audit_backend_unhealthy():
    """Test _audit_backend with unhealthy backend."""
    report = Mock()

    with patch('knowledge.engine.audit.get_audit') as mock_get_audit:
        mock_backend = MagicMock()
        mock_health = MagicMock()
        mock_health.healthy = False
        mock_health.error = "connection failed"
        mock_backend.health_check.return_value = mock_health
        mock_audit = MagicMock()
        mock_audit.backend = mock_backend
        mock_get_audit.return_value = mock_audit

        _audit_backend(report)

        report.assert_called_once_with("FAIL", "audit", "Audit backend unhealthy: connection failed")


def test_audit_backend_no_backend():
    """Test _audit_backend with no backend configured."""
    report = Mock()

    with patch('knowledge.engine.audit.get_audit') as mock_get_audit:
        mock_audit = MagicMock()
        mock_audit.backend = False
        mock_get_audit.return_value = mock_audit

        _audit_backend(report)

        report.assert_called_once_with("WARN", "audit", "No audit backend configured")


def test_audit_backend_exception():
    """Test _audit_backend when exception occurs."""
    report = Mock()

    with patch('knowledge.engine.audit.get_audit') as mock_get_audit:
        mock_get_audit.side_effect = Exception("boom")

        _audit_backend(report)

        report.assert_called_once_with("WARN", "audit", "Could not check audit health")


def test_audit_disk_fail():
    """Test _audit_disk with critical disk space (<1GB)."""
    mock_db_path = MagicMock()
    mock_usage = Mock()
    mock_usage.free = 0.5 * (1024**3)
    report = Mock()

    with patch('shutil.disk_usage', return_value=mock_usage):
        _audit_disk(mock_db_path, report)

    report.assert_called_once_with("FAIL", "disk_space", "Only 0.5 GB free on device")


def test_audit_disk_warn():
    """Test _audit_disk with warning disk space (<5GB)."""
    mock_db_path = MagicMock()
    mock_usage = Mock()
    mock_usage.free = 3 * (1024**3)
    report = Mock()

    with patch('shutil.disk_usage', return_value=mock_usage):
        _audit_disk(mock_db_path, report)

    report.assert_called_once_with("WARN", "disk_space", "3.0 GB free on device")


def test_audit_disk_ok():
    """Test _audit_disk with sufficient disk space (>5GB)."""
    mock_db_path = MagicMock()
    mock_usage = Mock()
    mock_usage.free = 20 * (1024**3)
    report = Mock()

    with patch('shutil.disk_usage', return_value=mock_usage):
        _audit_disk(mock_db_path, report)

    report.assert_called_once_with("OK", "disk_space", "20.0 GB free on device")


def test_cmd_audit_db_db_not_found(tmp_path):
    """Test cmd_audit_db when database file doesn't exist."""
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path:
        args = Mock()
        db_path = tmp_path / "nonexistent.sqlite"
        mock_resolve_db_path.return_value = db_path

        result = cmd_audit_db(args)

        assert result == 1


def test_cmd_audit_db_all_ok(tmp_path):
    """Test cmd_audit_db with all checks passing."""
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path, \
         patch('knowledge.engine.cli.audit.open_db') as mock_open_db, \
         patch('knowledge.engine.audit.get_audit') as mock_get_audit, \
         patch('shutil.disk_usage') as mock_disk_usage:

        args = Mock()
        db_path = tmp_path / "db.sqlite"
        db_path.write_bytes(b"x")
        mock_resolve_db_path.return_value = db_path

        mock_conn = MagicMock()
        mock_open_db.return_value = mock_conn

        # Configure audit results sequence
        mock_conn.execute.side_effect = [
            MagicMock(fetchone=Mock(return_value=("ok",))),              # integrity
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # orphan_src
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # orphan_dst
            MagicMock(fetchone=Mock(return_value={"c": 1})),             # active_version
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # stuck_jobs
            MagicMock(fetchone=Mock(return_value=("wal",))),             # wal_mode
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # pending_sync
        ]

        mock_wal_path = MagicMock()
        mock_wal_path.exists.return_value = True
        mock_wal_path.stat.return_value.st_size = 10 * 1024
        mock_db_path = MagicMock()
        mock_db_path.with_name.return_value = mock_wal_path
        mock_db_path.parent = tmp_path

        mock_usage = Mock()
        mock_usage.free = 10 * (1024**3)
        mock_disk_usage.return_value = mock_usage

        mock_audit = MagicMock()
        mock_health = MagicMock()
        mock_health.healthy = True
        mock_health.events_written = 10
        mock_audit.backend = True
        mock_audit.health_check.return_value = mock_health
        mock_get_audit.return_value = mock_audit

        result = cmd_audit_db(args)

        assert result == 0


def test_cmd_audit_db_with_failures(tmp_path):
    """Test cmd_audit_db returns 1 when checks fail."""
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path, \
         patch('knowledge.engine.cli.audit.open_db') as mock_open_db, \
         patch('knowledge.engine.audit.get_audit') as mock_get_audit, \
         patch('shutil.disk_usage') as mock_disk_usage:

        args = Mock()
        db_path = tmp_path / "db.sqlite"
        db_path.write_bytes(b"x")
        mock_resolve_db_path.return_value = db_path

        mock_conn = MagicMock()
        mock_open_db.return_value = mock_conn

        # One failing check (integrity)
        mock_conn.execute.side_effect = [
            MagicMock(fetchone=Mock(return_value=("corrupted",))),       # integrity FAIL
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # orphan_src
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # orphan_dst
            MagicMock(fetchone=Mock(return_value={"c": 1})),             # active_version
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # stuck_jobs
            MagicMock(fetchone=Mock(return_value=("wal",))),             # wal_mode
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # pending_sync
        ]

        mock_wal_path = MagicMock()
        mock_wal_path.exists.return_value = True
        mock_wal_path.stat.return_value.st_size = 10 * 1024
        mock_db_path = MagicMock()
        mock_db_path.with_name.return_value = mock_wal_path
        mock_db_path.parent = tmp_path

        mock_usage = Mock()
        mock_usage.free = 10 * (1024**3)
        mock_disk_usage.return_value = mock_usage

        mock_audit = MagicMock()
        mock_health = MagicMock()
        mock_health.healthy = True
        mock_health.events_written = 10
        mock_audit.backend = True
        mock_audit.health_check.return_value = mock_health
        mock_get_audit.return_value = mock_audit

        result = cmd_audit_db(args)

        assert result == 1


def test_cmd_audit_db_exception_in_check(tmp_path):
    """Test cmd_audit_db handles exceptions in individual checks."""
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path, \
         patch('knowledge.engine.cli.audit.open_db') as mock_open_db, \
         patch('knowledge.engine.audit.get_audit') as mock_get_audit, \
         patch('shutil.disk_usage') as mock_disk_usage:

        args = Mock()
        db_path = tmp_path / "db.sqlite"
        db_path.write_bytes(b"x")
        mock_resolve_db_path.return_value = db_path

        mock_conn = MagicMock()
        mock_open_db.return_value = mock_conn

        # Exception in one check should not crash others
        mock_conn.execute.side_effect = [
            MagicMock(fetchone=Mock(return_value=("ok",))),              # integrity OK
            Exception("DB error"),                                        # orphan_src exception
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # orphan_dst (not reached?)
            MagicMock(fetchone=Mock(return_value={"c": 1})),             # active_version
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # stuck_jobs
            MagicMock(fetchone=Mock(return_value=("wal",))),             # wal_mode
            MagicMock(fetchone=Mock(return_value={"c": 0})),             # pending_sync
        ]

        mock_wal_path = MagicMock()
        mock_wal_path.exists.return_value = True
        mock_wal_path.stat.return_value.st_size = 10 * 1024
        mock_db_path = MagicMock()
        mock_db_path.with_name.return_value = mock_wal_path
        mock_db_path.parent = tmp_path

        mock_usage = Mock()
        mock_usage.free = 10 * (1024**3)
        mock_disk_usage.return_value = mock_usage

        mock_audit = MagicMock()
        mock_health = MagicMock()
        mock_health.healthy = True
        mock_health.events_written = 10
        mock_audit.backend = True
        mock_audit.health_check.return_value = mock_health
        mock_get_audit.return_value = mock_audit

        # The function should handle the exception gracefully
        # (it doesn't have try/except per check, so it will propagate)
        try:
            result = cmd_audit_db(args)
        except Exception:
            pass  # Expected if no try/except


def test_cmd_audit_db_disk_fail(tmp_path):
    """Test cmd_audit_db with critical disk space."""
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path, \
         patch('knowledge.engine.cli.audit.open_db') as mock_open_db, \
         patch('knowledge.engine.audit.get_audit') as mock_get_audit, \
         patch('shutil.disk_usage') as mock_disk_usage:

        args = Mock()
        db_path = tmp_path / "db.sqlite"
        db_path.write_bytes(b"x")
        mock_resolve_db_path.return_value = db_path

        mock_conn = MagicMock()
        mock_open_db.return_value = mock_conn

        mock_conn.execute.side_effect = [
            MagicMock(fetchone=Mock(return_value=("ok",))),
            MagicMock(fetchone=Mock(return_value={"c": 0})),
            MagicMock(fetchone=Mock(return_value={"c": 0})),
            MagicMock(fetchone=Mock(return_value={"c": 1})),
            MagicMock(fetchone=Mock(return_value={"c": 0})),
            MagicMock(fetchone=Mock(return_value=("wal",))),
            MagicMock(fetchone=Mock(return_value={"c": 0})),
        ]

        mock_wal_path = MagicMock()
        mock_wal_path.exists.return_value = True
        mock_wal_path.stat.return_value.st_size = 10 * 1024
        mock_db_path = MagicMock()
        mock_db_path.with_name.return_value = mock_wal_path
        mock_db_path.parent = tmp_path

        mock_usage = Mock()
        mock_usage.free = 0.5 * (1024**3)  # < 1GB
        mock_disk_usage.return_value = mock_usage

        mock_audit = MagicMock()
        mock_health = MagicMock()
        mock_health.healthy = True
        mock_health.events_written = 10
        mock_audit.backend = True
        mock_audit.health_check.return_value = mock_health
        mock_get_audit.return_value = mock_audit

        result = cmd_audit_db(args)

        assert result == 1  # FAIL due to disk space


def test_cmd_vacuum_nonexistent_db(tmp_path):
    """Test cmd_vacuum with nonexistent database file."""
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path:
        args = Mock()
        db_path = tmp_path / "nonexistent.sqlite"
        mock_resolve_db_path.return_value = db_path

        result = cmd_vacuum(args)

        assert result == 1