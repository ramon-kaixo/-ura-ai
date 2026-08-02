"""Tests para infraestructura core: debate/lockfile, infra/state_manager."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from core.debate.lockfile import DebateLock
from core.infra.state_manager import STATE_FILE, clear_checkpoint, load_checkpoint, save_checkpoint


class TestDebateLock:
    def test_acquire_release(self, tmp_path) -> None:
        lock = DebateLock(str(tmp_path / "lock"))
        assert lock.acquire() is True
        assert lock._fd is not None
        lock.release()
        assert lock._fd is None

    def test_acquire_conflict(self, tmp_path) -> None:
        path = str(tmp_path / "lock")
        lock1 = DebateLock(path)
        lock2 = DebateLock(path)
        assert lock1.acquire() is True
        assert lock2.acquire() is False
        assert lock2._fd is None
        lock1.release()

    def test_acquire_error(self, tmp_path) -> None:
        lock = DebateLock(str(tmp_path / "lock"))
        with mock.patch("core.debate.lockfile.os.open", side_effect=OSError("permiso")):
            assert lock.acquire() is False
            assert lock._fd is None

    def test_release_sin_fd(self, tmp_path) -> None:
        lock = DebateLock(str(tmp_path / "lock"))
        lock.release()  # no debe fallar

    def test_context_manager(self, tmp_path) -> None:
        lock = DebateLock(str(tmp_path / "lock"))
        with lock:
            assert lock._fd is not None
        assert lock._fd is None


class TestStateManager:
    def test_save_load_roundtrip(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "state.json"
        monkeypatch.setattr("core.infra.state_manager.STATE_FILE", str(f))
        save_checkpoint("t1", "archivo.py", "contenido", attempt=3)
        record = load_checkpoint()
        assert record["task_id"] == "t1"
        assert record["target_file"] == "archivo.py"
        assert record["content"] == "contenido"
        assert record["attempt"] == 3
        assert "timestamp" in record

    def test_load_sin_archivo(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.infra.state_manager.STATE_FILE", str(tmp_path / "nope.json"))
        assert load_checkpoint() is None

    def test_load_corrupto(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "state.json"
        f.write_text("no es json")
        monkeypatch.setattr("core.infra.state_manager.STATE_FILE", str(f))
        assert load_checkpoint() is None

    def test_save_error(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "state.json"
        monkeypatch.setattr("core.infra.state_manager.STATE_FILE", str(f))
        with mock.patch("builtins.open", side_effect=OSError("ro")):
            save_checkpoint("t1", "f", "c")  # no debe lanzar

    def test_clear(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "state.json"
        f.write_text("{}")
        monkeypatch.setattr("core.infra.state_manager.STATE_FILE", str(f))
        clear_checkpoint()
        assert not f.exists()

    def test_clear_sin_archivo(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.infra.state_manager.STATE_FILE", str(tmp_path / "nope.json"))
        clear_checkpoint()  # no debe fallar

    def test_clear_error(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "state.json"
        f.write_text("{}")
        monkeypatch.setattr("core.infra.state_manager.STATE_FILE", str(f))
        with mock.patch("core.infra.state_manager.os.remove", side_effect=OSError("ro")):
            clear_checkpoint()  # no debe lanzar
