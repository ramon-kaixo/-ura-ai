"""Tests for scripts/pro/backup_f26_memory.py."""

from unittest.mock import MagicMock, patch

import pytest

from scripts.pro.backup_f26_memory import cmd_backup, cmd_restore, main


class TestCmdBackup:
    @patch("motor.memory.save_snapshot")
    @patch("motor.memory.Memory")
    def test_backup_calls_save_snapshot(self, mock_memory_cls, mock_save):
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory

        cmd_backup("/tmp/test_backup.json")

        mock_memory_cls.assert_called_once()
        mock_save.assert_called_once_with(mock_memory, "/tmp/test_backup.json")


class TestCmdRestore:
    @patch("motor.memory.load_snapshot")
    def test_restore_calls_load_snapshot(self, mock_load, tmp_path):
        p = tmp_path / "backup.json"
        p.write_text("{}")

        cmd_restore(str(p))

        mock_load.assert_called_once_with(str(p))

    def test_restore_missing_file(self, tmp_path):
        missing = tmp_path / "no_existe.json"
        with pytest.raises(SystemExit) as exc:
            cmd_restore(str(missing))
        assert exc.value.code == 1


class TestMain:
    @patch("scripts.pro.backup_f26_memory.cmd_backup")
    def test_main_backup(self, mock_backup, monkeypatch):
        monkeypatch.setattr("sys.argv", ["backup_f26_memory.py", "backup", "--path", "/tmp/b.json"])
        main()
        mock_backup.assert_called_once_with("/tmp/b.json")

    @patch("scripts.pro.backup_f26_memory.cmd_restore")
    def test_main_restore(self, mock_restore, monkeypatch):
        monkeypatch.setattr("sys.argv", ["backup_f26_memory.py", "restore", "--path", "/tmp/r.json"])
        main()
        mock_restore.assert_called_once_with("/tmp/r.json")

    def test_main_no_args(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["backup_f26_memory.py"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_main_invalid_command(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["backup_f26_memory.py", "invalid"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
