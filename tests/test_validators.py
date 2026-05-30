"""Tests for core/validators.py — security and dependency validation."""

import pytest
from unittest.mock import patch, MagicMock

# Check if security tools are available
try:
    import subprocess

    result = subprocess.run(["pip-audit", "--version"], capture_output=True, text=True, timeout=5)
    HAS_PIP_AUDIT = result.returncode == 0
except:
    HAS_PIP_AUDIT = False

try:
    import subprocess

    result = subprocess.run(["safety", "--version"], capture_output=True, text=True, timeout=5)
    HAS_SAFETY = result.returncode == 0
except:
    HAS_SAFETY = False

try:
    import subprocess

    result = subprocess.run(["bandit", "--version"], capture_output=True, text=True, timeout=5)
    HAS_BANDIT = result.returncode == 0
except:
    HAS_BANDIT = False

try:
    pass

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# Skip entire module if all security tools are missing
pytestmark = pytest.mark.skipif(
    not (HAS_PIP_AUDIT or HAS_SAFETY or HAS_BANDIT or HAS_WEBSOCKETS),
    reason="All security tools (pip-audit, safety, bandit, websockets) are missing",
)


class TestValidateSecuritySetup:
    """validate_security_setup() — checks security tools are installed."""

    def test_returns_list(self):
        from core.validators import validate_security_setup

        result = validate_security_setup()
        assert isinstance(result, list)

    def test_returns_non_empty_list(self):
        from core.validators import validate_security_setup

        result = validate_security_setup()
        assert len(result) > 0

    def test_all_items_are_strings(self):
        from core.validators import validate_security_setup

        result = validate_security_setup()
        for item in result:
            assert isinstance(item, str)

    def test_items_have_emoji_prefix(self):
        from core.validators import validate_security_setup

        result = validate_security_setup()
        for item in result:
            assert item.startswith(("✅", "⚠️"))

    @patch("subprocess.run")
    def test_handles_subprocess_success(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(returncode=0)
        from core.validators import validate_security_setup

        result = validate_security_setup()
        assert any("disponible" in item for item in result)

    @patch("subprocess.run")
    def test_handles_subprocess_failure(self, mock_run: MagicMock):
        mock_run.side_effect = Exception("command not found")
        from core.validators import validate_security_setup

        result = validate_security_setup()
        assert any("no instalado" in item for item in result)


class TestCheckDependencies:
    """check_dependencies() — validates optional dependencies are present."""

    def test_returns_tuple(self):
        from core.validators import check_dependencies

        result = check_dependencies()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_all_deps_found_on_real_environment(self):
        pytest.importorskip("redis", reason="redis no instalado - dependencia opcional")

        from core.validators import check_dependencies

        all_ok, missing = check_dependencies()
        assert isinstance(all_ok, bool)
        assert isinstance(missing, list)
        # Filter out optional deps (ollama, redis) - they can be missing
        optional_deps = {"ollama", "redis"}
        missing_critical = [dep for dep in missing if dep not in optional_deps]
        assert missing_critical == [], f"Missing critical deps: {missing_critical}"
