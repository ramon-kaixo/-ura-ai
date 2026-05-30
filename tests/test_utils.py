"""Tests for core/utils.py — shared utilities module."""

from pathlib import Path
from core.utils import safe_execute, sanitize_input, sanitize_path, validate_file_path


class TestSafeExecute:
    """safe_execute(func, fallback=None) — wraps function execution safely."""

    def test_returns_result_on_success(self):
        result = safe_execute(lambda: "ok")
        assert result == "ok"

    def test_returns_fallback_on_exception(self):
        def _bomb():
            raise ValueError("fail")

        result = safe_execute(_bomb, fallback=None)
        assert result is None

    def test_without_fallback_returns_none_on_exception(self):
        def _bomb():
            raise RuntimeError("fail")

        result = safe_execute(_bomb)
        assert result is None


class TestSanitizeInput:
    """sanitize_input(user_input) — blocks dangerous shell patterns."""

    def test_passes_clean_input(self):
        assert sanitize_input("hola mundo") == "hola mundo"

    def test_blocks_rm_rf(self):
        result = sanitize_input("ejecuta rm -rf /tmp")
        assert "no permitido" in result

    def test_blocks_sudo(self):
        result = sanitize_input("sudo reboot")
        assert "no permitido" in result

    def test_blocks_chmod_777(self):
        result = sanitize_input("chmod 777 .")
        assert "no permitido" in result

    def test_blocks_dd_if_zero(self):
        result = sanitize_input("dd if=/dev/zero of=/dev/sda")
        assert "no permitido" in result

    def test_blocks_fork_bomb(self):
        result = sanitize_input(":(){ :|:& };:")
        assert "no permitido" in result

    def test_blocks_mkfs(self):
        result = sanitize_input("mkfs.ext4 /dev/sda")
        assert "no permitido" in result

    def test_handles_empty_input(self):
        assert sanitize_input("") == ""
        assert sanitize_input(None) is None

    def test_exact_pattern_blocked(self):
        result = sanitize_input("sudo rm -rf /")
        assert "no permitido" in result


class TestSanitizePath:
    """sanitize_path(path) — removes dangerous path characters."""

    def test_strips_dot_dot(self):
        assert ".." not in sanitize_path("../../../etc/passwd")

    def test_strips_tilde(self):
        assert "~" not in sanitize_path("~/secret")

    def test_strips_dollar(self):
        assert "$" not in sanitize_path("$(whoami)")

    def test_strips_backtick(self):
        assert "`" not in sanitize_path("`whoami`")

    def test_strips_semicolon(self):
        assert ";" not in sanitize_path("; rm -rf /")


class TestValidateFilePath:
    """validate_file_path(file_path, allowed_dirs) — path containment check."""

    def test_file_inside_allowed_dir(self, tmp_path):
        file_path = tmp_path / "safe.txt"
        file_path.write_text("ok")
        assert validate_file_path(file_path, [tmp_path]) is True

    def test_file_outside_allowed_dir(self, tmp_path):
        outside = Path("/etc/passwd")
        assert validate_file_path(outside, [tmp_path]) is False

    def test_nonexistent_path_inside_allowed_dir_still_valid(self, tmp_path):
        fake = tmp_path / "nonexistent.txt"
        result = validate_file_path(fake, [tmp_path])
        assert result is True
