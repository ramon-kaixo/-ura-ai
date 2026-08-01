"""Tests para mantenimiento/ura_maintenance.py — Fase 4 (B2).

Importa el módulo una vez (tiene side-effects de logging tolerables);
todo I/O real se simula con monkeypatch.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import mantenimiento.ura_maintenance as um
from mantenimiento.ura_maintenance import (
    DEFAULT_CONFIG,
    LinuxCleaner,
    MacCleaner,
    MaintenanceConfig,
    MaintenanceOrchestrator,
    SecurityValidator,
    SystemCleaner,
    load_config,
)


class _FakeResult:
    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def _config(tmp_path: Path) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["allowed_temp_dirs"] = [str(tmp_path / "tmp")]
    cfg["allowed_log_dirs"] = [str(tmp_path / "logs")]
    cfg["retention_days"]["logs"] = 0
    return cfg


class TestLoadConfig:
    def test_default_when_no_path(self) -> None:
        assert load_config() == DEFAULT_CONFIG

    def test_missing_file_ignored(self) -> None:
        assert load_config("/no/existe/config.json") == DEFAULT_CONFIG

    def test_invalid_json_warns(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{no json")
        assert load_config(str(bad)) == DEFAULT_CONFIG

    def test_merges_user_config(self, tmp_path: Path) -> None:
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"log_dir": "/tmp/x", "thresholds": {"docker_images": 99}}))
        result = load_config(str(cfg))
        assert result["log_dir"] == "/tmp/x"
        assert result["thresholds"]["docker_images"] == 99
        assert result["exclude_patterns"] == DEFAULT_CONFIG["exclude_patterns"]


class TestSecurityValidator:
    def test_symlink_rejected(self, tmp_path: Path) -> None:
        target = tmp_path / "real"
        target.write_text("x")
        link = tmp_path / "link"
        link.symlink_to(target)
        validator = SecurityValidator(_config(tmp_path))
        ok, reason = validator.is_safe_to_delete(str(link))
        assert not ok
        assert "Symlink" in reason

    def test_not_owner_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _config(tmp_path)
        file = tmp_path / "tmp" / "a.txt"
        file.parent.mkdir(parents=True)
        file.write_text("x")
        validator = SecurityValidator(cfg)
        monkeypatch.setattr(validator, "current_uid", -1)
        ok, _reason = validator.is_safe_to_delete(str(file))
        assert not ok

    def test_stat_error_propagates_from_is_symlink(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Hallazgo F4: is_safe_to_delete lanza OSError si stat falla antes del
        # try/except (is_symlink() -> lstat() no está protegido). Comportamiento
        # actual documentado; candidato de corrección para Fase 5.
        validator = SecurityValidator(_config(tmp_path))

        def boom(*_a: object, **_k: object) -> None:
            raise OSError("nope")

        monkeypatch.setattr(Path, "stat", boom)
        with pytest.raises(OSError):
            validator.is_safe_to_delete("/no/existe")

    def test_exclude_pattern_matches(self, tmp_path: Path) -> None:
        file = tmp_path / "tmp" / "data.db"
        file.parent.mkdir(parents=True)
        file.write_text("x")
        validator = SecurityValidator(_config(tmp_path))
        ok, reason = validator.is_safe_to_delete(str(file))
        assert not ok
        assert "exclude pattern" in reason

    def test_outside_allowed_dir(self, tmp_path: Path) -> None:
        file = tmp_path / "otro" / "a.txt"
        file.parent.mkdir(parents=True)
        file.write_text("x")
        validator = SecurityValidator(_config(tmp_path))
        ok, reason = validator.is_safe_to_delete(str(file))
        assert not ok
        assert "Outside allowed" in reason

    def test_safe_file_passes(self, tmp_path: Path) -> None:
        file = tmp_path / "tmp" / "a.txt"
        file.parent.mkdir(parents=True)
        file.write_text("x")
        validator = SecurityValidator(_config(tmp_path))
        ok, _reason = validator.is_safe_to_delete(str(file))
        assert ok


class TestMaintenanceConfig:
    def test_fields_copied(self) -> None:
        cfg = MaintenanceConfig(DEFAULT_CONFIG)
        assert cfg.exclude_patterns == DEFAULT_CONFIG["exclude_patterns"]
        assert cfg.thresholds == DEFAULT_CONFIG["thresholds"]


class TestSystemCleaner:
    def test_get_disk_usage(self) -> None:
        cfg = MaintenanceConfig(DEFAULT_CONFIG)
        validator = SecurityValidator(DEFAULT_CONFIG)
        cleaner = SystemCleaner(cfg, validator)
        usage = cleaner.get_disk_usage("/")
        assert "total" in usage and "used" in usage and "percent" in usage

    def test_get_disk_usage_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = MaintenanceConfig(DEFAULT_CONFIG)
        cleaner = SystemCleaner(cfg, SecurityValidator(DEFAULT_CONFIG))

        def boom(_p: str) -> None:
            raise OSError("no disk")

        monkeypatch.setattr("shutil.disk_usage", boom)
        assert cleaner.get_disk_usage("/") == {}

    def test_should_clean(self) -> None:
        cfg = MaintenanceConfig(DEFAULT_CONFIG)
        cleaner = SystemCleaner(cfg, SecurityValidator(DEFAULT_CONFIG))
        assert cleaner.should_clean(11.0, "docker_images") is True
        assert cleaner.should_clean(1.0, "docker_images") is False

    def test_record_operation(self) -> None:
        cfg = MaintenanceConfig(DEFAULT_CONFIG)
        cleaner = SystemCleaner(cfg, SecurityValidator(DEFAULT_CONFIG))
        cleaner.record_operation("prune", 1.5)
        assert cleaner.operations[0]["operation"] == "prune"
        assert cleaner.space_freed == 1.5

    def test_safe_remove_unsafe_returns_false(self, tmp_path: Path) -> None:
        cfg = MaintenanceConfig(_config(tmp_path))
        cleaner = SystemCleaner(cfg, SecurityValidator(_config(tmp_path)))
        assert cleaner.safe_remove("/etc/passwd") is False

    def test_safe_remove_oserror(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _config(tmp_path)
        file = tmp_path / "tmp" / "a.txt"
        file.parent.mkdir(parents=True)
        file.write_text("x")
        cleaner = SystemCleaner(MaintenanceConfig(cfg), SecurityValidator(cfg))

        def boom(_p: str) -> None:
            raise OSError("perm")

        monkeypatch.setattr(os, "remove", boom)
        assert cleaner.safe_remove(str(file)) is False

    def test_safe_rmtree(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path)
        target = tmp_path / "tmp" / "dir"
        target.mkdir(parents=True)
        (target / "f.txt").write_text("x")
        cleaner = SystemCleaner(MaintenanceConfig(cfg), SecurityValidator(cfg))
        assert cleaner.safe_rmtree(str(target)) is True
        assert not target.exists()


class TestLinuxCleaner:
    def _cleaner(self, tmp_path: Path) -> LinuxCleaner:
        cfg = _config(tmp_path)
        return LinuxCleaner(MaintenanceConfig(cfg), SecurityValidator(cfg))

    def test_clean_docker_not_installed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: object, **_k: object) -> None:
            raise FileNotFoundError

        monkeypatch.setattr(subprocess, "run", boom)
        assert self._cleaner(tmp_path).clean_docker() == 0

    def test_clean_docker_reclaimed_gb(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult("Total reclaimed space: 1.5GB", 0))
        cleaner = self._cleaner(tmp_path)
        assert cleaner.clean_docker() == 1.5
        assert cleaner.operations[0]["operation"] == "docker_prune"

    def test_clean_docker_reclaimed_mb(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult("Total reclaimed space: 512MB", 0))
        cleaner = self._cleaner(tmp_path)
        assert cleaner.clean_docker() == pytest.approx(0.5, abs=1e-3)

    def test_clean_docker_no_match(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult("nada", 0))
        assert self._cleaner(tmp_path).clean_docker() == 0

    def test_clean_docker_timeout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: object, **_k: object) -> None:
            raise subprocess.TimeoutExpired("docker", 300)

        monkeypatch.setattr(subprocess, "run", boom)
        assert self._cleaner(tmp_path).clean_docker() == 0

    def test_clean_apt_cache_no_apt(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda _c: None)
        assert self._cleaner(tmp_path).clean_apt_cache() == 0

    def test_clean_apt_cache_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda _c: "/usr/bin/apt-get")
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult())
        cleaner = self._cleaner(tmp_path)
        usages = iter([{"used": 10.0}, {"used": 8.0}])
        monkeypatch.setattr(cleaner, "get_disk_usage", lambda: next(usages))
        assert cleaner.clean_apt_cache() == 2.0
        assert cleaner.operations[0]["operation"] == "apt_cache"

    def test_clean_pip_cache_no_pip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda _c: None)
        assert self._cleaner(tmp_path).clean_pip_cache() == 0

    def test_clean_pip_cache_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda c: "/usr/bin/pip3" if c == "pip3" else None)
        cache_file = tmp_path / ".cache" / "pip" / "big.whl"

        def fake_purge(*_a: object, **_k: object) -> _FakeResult:
            cache_file.unlink(missing_ok=True)
            return _FakeResult("ok", 0)

        monkeypatch.setattr(subprocess, "run", fake_purge)
        cache_dir = tmp_path / ".cache" / "pip"
        cache_dir.mkdir(parents=True)
        cache_file.write_text("x" * 2048)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        cleaner = self._cleaner(tmp_path)
        freed = cleaner.clean_pip_cache()
        assert freed == pytest.approx((2048 / (1024**3)), abs=1e-9)
        assert cleaner.operations[0]["operation"] == "pip_cache"

    def test_clean_old_logs_zero_freed_but_removes(self, tmp_path: Path) -> None:
        # Hallazgo F4: el fichero se borra (safe_remove ok) pero el tamaño se
        # lee DESPUÉS del borrado -> stat lanza FileNotFoundError -> except
        # OSError -> total_freed nunca suma -> siempre 0. Bug candidato F5.
        cfg = _config(tmp_path)
        log_dir = tmp_path / "logs" / "sub"
        log_dir.mkdir(parents=True)
        old = log_dir / "viejo.log"
        old.write_text("x" * 1024)
        old_time = 1_000_000_000  # 2001 — más viejo que retention 0
        os.utime(old, (old_time, old_time))
        cleaner = LinuxCleaner(MaintenanceConfig(cfg), SecurityValidator(cfg))
        assert cleaner.clean_old_logs() == 0
        assert not old.exists()

    def test_clean_temp_files_zero_by_design(self, tmp_path: Path) -> None:
        # Hallazgo F4: el tamaño se lee DESPUÉS de os.remove -> FileNotFoundError
        # -> except OSError -> total_freed nunca suma. Bug candidato F5.
        cfg = _config(tmp_path)
        tmp_dir = tmp_path / "tmp"
        tmp_dir.mkdir(parents=True)
        target = tmp_dir / "f.txt"
        target.write_text("x" * 2048)
        cleaner = LinuxCleaner(MaintenanceConfig(cfg), SecurityValidator(cfg))
        assert cleaner.clean_temp_files() == 0
        assert not target.exists()


class TestMaintenanceOrchestrator:
    def test_get_cleaner_linux(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("platform.system", lambda: "Linux")
        orc = MaintenanceOrchestrator()
        assert isinstance(orc.cleaner, LinuxCleaner)

    def test_get_cleaner_darwin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        orc = MaintenanceOrchestrator()
        assert isinstance(orc.cleaner, MacCleaner)

    def test_get_cleaner_unsupported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("platform.system", lambda: "Windows")
        with pytest.raises(ValueError):
            MaintenanceOrchestrator()

    def test_run_maintenance(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr(um, "LOG_DIR", tmp_path)
        orc = MaintenanceOrchestrator()
        monkeypatch.setattr(orc.cleaner, "get_disk_usage", lambda: {"used": 10.0, "total": 100.0, "percent": 10.0})

        def fake_clean(name: str) -> object:
            def _run() -> float:
                orc.cleaner.record_operation(name, 0.5)
                return 0.5

            return _run

        for method in ("clean_docker", "clean_apt_cache", "clean_pip_cache", "clean_old_logs", "clean_temp_files"):
            monkeypatch.setattr(orc.cleaner, method, fake_clean(method))
        results = orc.run_maintenance()
        assert results["space_freed_gb"] == 2.5
        assert len(results["operations"]) == 5
        saved = list(tmp_path.glob("maintenance_results_*.json"))
        assert len(saved) == 1

    def test_save_results_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(um, "LOG_DIR", tmp_path / "no_existe_rc")
        orc = MaintenanceOrchestrator()
        monkeypatch.setattr(orc, "results", {"a": 1})

        def boom(*_a: object, **_k: object) -> None:
            raise OSError("no write")

        monkeypatch.setattr("builtins.open", boom)
        orc._save_results()  # no lanza

    def test_main_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeOrc:
            def run_maintenance(self) -> dict:
                return {"space_freed_gb": 1.0}

        monkeypatch.setattr(um, "MaintenanceOrchestrator", FakeOrc)
        assert um.main() == 0

    def test_main_returns_one_on_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Boom:
            def run_maintenance(self) -> dict:
                raise RuntimeError("boom")

        monkeypatch.setattr(um, "MaintenanceOrchestrator", Boom)
        assert um.main() == 1
