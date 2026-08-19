"""Tests de cobertura para knowledge/engine/lock.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.engine.lock import LockAcquisitionError, compile_lock


def test_compile_lock_adquiere_y_libera(tmp_path: Path) -> None:
    lock_file = tmp_path / "sub" / "compile.lock"
    with compile_lock(lock_file):
        assert lock_file.exists()
    assert lock_file.exists()


def test_compile_lock_crea_padre(tmp_path: Path) -> None:
    with compile_lock(tmp_path / "a" / "b" / "l.lock"):
        assert (tmp_path / "a" / "b").is_dir()


def test_compile_lock_exclusivo(tmp_path: Path) -> None:
    lock_file = tmp_path / "c.lock"
    with compile_lock(lock_file), pytest.raises(LockAcquisitionError), compile_lock(lock_file):
        pytest.fail("no debería adquirirse")


def test_compile_lock_liberado_despues(tmp_path: Path) -> None:
    lock_file = tmp_path / "d.lock"
    with compile_lock(lock_file):
        pass
    with compile_lock(lock_file):
        pass


def test_compile_lock_error_es_exception() -> None:
    assert issubclass(LockAcquisitionError, Exception)


def test_compile_lock_release_suppress_oserror(tmp_path: Path, monkeypatch) -> None:
    import fcntl

    lock_file = tmp_path / "e.lock"
    calls: list[tuple] = []

    def _flock(fd, op):
        calls.append(op)
        if op == fcntl.LOCK_UN:
            raise OSError("fd ya cerrado")
        return fcntl.flock(fd, op)

    monkeypatch.setattr("knowledge.engine.lock.fcntl.flock", _flock)
    with compile_lock(lock_file):
        pass
    assert len(calls) >= 2
