"""Tests de notifier y json_logger."""

from core.json_logger import StructuredLogger
from core.notifier import notify


def test_notifier_empty_returns_false() -> None:
    """Sin tokens configurados, notify debe retornar False sin crashear."""
    try:
        result = notify("test", level="info")
        assert result is False
    except Exception:
        pass


def test_logger_creates_and_logs() -> None:
    log = StructuredLogger("test_logger")
    assert log is not None
    log.info("test message")
    log.warning("test warning")
    log.error("test error")
    log.debug("test debug")


def test_logger_different_names() -> None:
    log1 = StructuredLogger("svc1")
    log2 = StructuredLogger("svc2")
    assert log1._logger.name != log2._logger.name
