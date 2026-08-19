import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add the project root to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from knowledge.engine.cli.audit import cmd_vacuum, _audit_integrity, _audit_orphans, _audit_active_version


def test_cmd_vacuum_success(tmp_path):
    """Test cmd_vacuum function with successful database operation."""
    # Mock the _resolve_db_path and open_db functions
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path, \
         patch('knowledge.engine.cli.audit.open_db') as mock_open_db:
        
        # Setup mocks
        args = Mock()
        args.db = '/mock/path/to/db'
        db_path = tmp_path / "db.sqlite"
        db_path.write_bytes(b"x")
        mock_resolve_db_path.return_value = db_path
        mock_db_conn = MagicMock()
        mock_open_db.return_value = mock_db_conn
        
        # Call the function
        result = cmd_vacuum(args)
        
        # Assert
        assert result == 0
        mock_resolve_db_path.assert_called_once_with(args)
        mock_open_db.assert_called_once_with(db_path)
        mock_db_conn.execute.assert_called()


def test_cmd_vacuum_failure(tmp_path):
    """Test cmd_vacuum function with failed database operation."""
    # Mock the _resolve_db_path and open_db functions
    with patch('knowledge.engine.cli.audit._resolve_db_path') as mock_resolve_db_path, \
         patch('knowledge.engine.cli.audit.open_db') as mock_open_db:
        
        # Setup mocks
        args = Mock()
        args.db = '/mock/path/to/db'
        db_path = tmp_path / "db.sqlite"
        db_path.write_bytes(b"x")
        mock_resolve_db_path.return_value = db_path
        mock_db_conn = MagicMock()
        mock_open_db.return_value = mock_db_conn
        mock_db_conn.execute.side_effect = Exception("Database error")
        
        # Call the function
        result = cmd_vacuum(args)
        
        # Assert
        assert result == 1
        mock_resolve_db_path.assert_called_once_with(args)
        mock_open_db.assert_called_once_with(db_path)
        mock_db_conn.execute.assert_called()


def test_audit_integrity():
    """Test _audit_integrity function."""
    with patch('knowledge.engine.cli.audit.open_db') as mock_open_db:
        # Setup mocks
        mock_db_conn = MagicMock()
        mock_open_db.return_value.__enter__.return_value = mock_db_conn
        
        # Mock the database results
        mock_db_conn.execute.return_value.fetchall.return_value = [
            ('table1', 10),
            ('table2', 5)
        ]
        
        # Setup report function
        report_mock = Mock()
        
        # Call the function
        _audit_integrity(mock_db_conn, report_mock)
        
        # Assert
        mock_db_conn.execute.assert_called_once_with("PRAGMA integrity_check")
        report_mock.assert_called()


def test_audit_orphans():
    """Test _audit_orphans function."""
    with patch('knowledge.engine.cli.audit.open_db') as mock_open_db:
        # Setup mocks
        mock_db_conn = MagicMock()
        mock_open_db.return_value.__enter__.return_value = mock_db_conn
        
        # Mock the database results for orphaned records
        mock_db_conn.execute.return_value.fetchall.return_value = [
            (1, 'fragment1'),
            (2, 'fragment2')
        ]
        
        # Setup report function
        report_mock = Mock()
        
        # Call the function
        _audit_orphans(mock_db_conn, report_mock)
        
        # Assert
        mock_db_conn.execute.assert_called()
        report_mock.assert_called()


def test_audit_active_version():
    """Test _audit_active_version function."""
    with patch('knowledge.engine.cli.audit.open_db') as mock_open_db:
        # Setup mocks
        mock_db_conn = MagicMock()
        mock_open_db.return_value.__enter__.return_value = mock_db_conn
        
        # Mock the database results for active version
        mock_db_conn.execute.return_value.fetchall.return_value = [
            ('version_1', 100),
            ('version_2', 50)
        ]
        
        # Setup report function
        report_mock = Mock()
        
        # Call the function
        _audit_active_version(mock_db_conn, report_mock)
        
        # Assert
        mock_db_conn.execute.assert_called()
        report_mock.assert_called()


def test_audit_active_version_empty():
    """Test _audit_active_version function with no results."""
    with patch('knowledge.engine.cli.audit.open_db') as mock_open_db:
        # Setup mocks
        mock_db_conn = MagicMock()
        mock_open_db.return_value.__enter__.return_value = mock_db_conn
        
        # Mock the database results for empty active version
        mock_db_conn.execute.return_value.fetchall.return_value = []
        
        # Setup report function
        report_mock = Mock()
        
        # Call the function
        _audit_active_version(mock_db_conn, report_mock)
        
        # Assert
        mock_db_conn.execute.assert_called()
        report_mock.assert_called()

