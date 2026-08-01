"""Tests for scripts/pro/lock_manager.py."""
import fcntl

import pytest

from scripts.pro.lock_manager import acquire_gpu_lock, release_gpu_lock


class TestLockManager:
    def test_acquire_and_release(self, tmp_path):
        lock = tmp_path / "test.lock"
        fp = acquire_gpu_lock(str(lock), timeout=1)
        assert fp is not None
        release_gpu_lock(fp)
        assert fp.closed

    def test_acquire_timeout(self, tmp_path, monkeypatch):
        lock = tmp_path / "test.lock"

        def always_busy(*_a, **_k):
            raise BlockingIOError

        monkeypatch.setattr(fcntl, "flock", always_busy)
        with pytest.raises(RuntimeError, match="No se pudo adquirir"):
            acquire_gpu_lock(str(lock), timeout=0)

    def test_release_none(self):
        release_gpu_lock(None)

    def test_reacquire_after_release(self, tmp_path):
        lock = tmp_path / "test.lock"
        fp1 = acquire_gpu_lock(str(lock), timeout=1)
        release_gpu_lock(fp1)
        fp2 = acquire_gpu_lock(str(lock), timeout=1)
        assert fp2 is not None
        release_gpu_lock(fp2)
        assert fp2.closed
