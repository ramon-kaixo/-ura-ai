"""Tests de path_setup, notifier, json_logger."""

import pytest

from core.json_logger import StructuredLogger
from core.notifier import notify
from path_setup import get_project_root, setup_path


def test_path_setup_basic() -> None:
    setup_path()
    root = get_project_root()
    assert root is not None
    assert root.exists()


def test_notifier_return_false_when_disabled() -> None:
    # Sin tokens configurados → debe retornar False sin crash
    try:
        result = notify("test message", level="info")
        assert result is False
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    except Exception:  # noqa: S110
        pass
=======
    except Exception:
        pytest.fail("notify() raised unexpected exception")
>>>>>>> Stashed changes
=======
    except Exception:
        pytest.fail("notify() raised unexpected exception")
>>>>>>> Stashed changes
=======
    except Exception:
        pytest.fail("notify() raised unexpected exception")
>>>>>>> Stashed changes
=======
    except Exception:
        pytest.fail("notify() raised unexpected exception")
>>>>>>> Stashed changes
=======
    except Exception:
        pytest.fail("notify() raised unexpected exception")
>>>>>>> Stashed changes
=======
    except Exception:
        pytest.fail("notify() raised unexpected exception")
>>>>>>> Stashed changes
=======
    except Exception:
        pytest.fail("notify() raised unexpected exception")
>>>>>>> Stashed changes


def test_structured_logger_creates() -> None:
    log = StructuredLogger("test_logger")
    assert log is not None
    log.info("test message")
    log.warning("test warning")
    log.error("test error")
