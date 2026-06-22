"""Tests de json_logger."""

from core.json_logger import JsonFormatter, StructuredLogger


def test_json_formatter() -> None:
    formatter = JsonFormatter()
    assert formatter is not None


def test_structured_logger() -> None:
    log = StructuredLogger("test")
    assert log is not None
    log.info("test message")
    log.warning("test warning")
