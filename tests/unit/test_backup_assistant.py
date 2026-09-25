"""Tests for scripts/pro/backup_assistant.py."""
from pathlib import Path

import pytest

from scripts.pro.backup_assistant import backup, restore


class TestBackupAssistant:
    @pytest.mark.unit
    def test_backup_creates_dir_and_log(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "test.db").write_text("x")
        monkeypatch.setattr("scripts.pro.backup_assistant.DATA_DIR", data_dir)
        monkeypatch.setattr("scripts.pro.backup_assistant.BACKUP_DIR", tmp_path / "backups")
        result = backup()
        assert Path(result).exists()
        assert (Path(result) / "test.db").exists()
        assert (Path(result) / "backup_log.txt").exists()

    @pytest.mark.unit
    def test_backup_empty_data_dir(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setattr("scripts.pro.backup_assistant.DATA_DIR", data_dir)
        monkeypatch.setattr("scripts.pro.backup_assistant.BACKUP_DIR", tmp_path / "backups")
        result = backup()
        assert Path(result).exists()
        assert (Path(result) / "backup_log.txt").exists()

    @pytest.mark.unit
    def test_restore_copies_files(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        backup_dir = tmp_path / "backup_20240101_120000"
        backup_dir.mkdir()
        (backup_dir / "test.db").write_text("restored")
        monkeypatch.setattr("scripts.pro.backup_assistant.DATA_DIR", data_dir)
        restore(str(backup_dir))
        assert (data_dir / "test.db").exists()
        assert (data_dir / "test.db").read_text() == "restored"

    @pytest.mark.unit
    def test_restore_invalid_path_exits(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("scripts.pro.backup_assistant.DATA_DIR", tmp_path / "data")
        with pytest.raises(SystemExit) as exc:
            restore(str(tmp_path / "no_existe"))
        assert exc.value.code == 1
