import os  # noqa: EXE002
import sys
from pathlib import Path

import pytest

# Avoid /root/.ura/run/ crash in docker read-only filesystem during test collection
os.environ.setdefault("URA_STATE_DIR", "/tmp/.ura_test_run")
os.environ.setdefault("URA_LOGS_DIR", "/tmp/.ura_test_logs")
os.environ.setdefault("URA_DATA_DIR", "/tmp/.ura_test_data")
os.environ.setdefault("MOCHILA_COST_FILE", "/tmp/.ura_test_data/cost_tracker.jsonl")
os.environ.setdefault("MOCHILA_HEALTH_FILE", "/tmp/.ura_test_data/provider_health.json")

# Add sandbox packages if available (httpx, etc installed in docker to .sandbox_packages)
_sandbox_pkgs = Path(__file__).parent.parent / ".sandbox_packages"
if _sandbox_pkgs.exists():
    sys.path.insert(0, str(_sandbox_pkgs))

# TestServer tests depend on mochila_server which imports core.memoria.rastreadores.saber
# This module was removed during refactoring. Skip if not available.
try:
    import core.memoria.rastreadores.saber  # noqa: F401

    _HAVE_RASTR = True
except ImportError:
    _HAVE_RASTR = False


def pytest_collection_modifyitems(items) -> None:
    for item in items:
        # Skip file_read tests in docker sandbox (hardcoded /home/ramon/URA path)
        if "test_read_project_file" in item.nodeid:
            item.add_marker(
                pytest.mark.skip(
                    reason="Requiere ruta /home/ramon/URA/ura_ia_1972 (solo GX10)",
                ),
            )
        if not _HAVE_RASTR and item.nodeid.startswith("tests/test_mochila.py::TestServer"):
            item.add_marker(
                pytest.mark.skip(
                    reason="TestServer depende de core.memoria.rastreadores.saber (eliminado)",
                ),
            )
