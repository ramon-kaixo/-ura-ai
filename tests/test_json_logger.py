
"""Tests de json_logger."""
from core.json_logger import StructuredLogger, JsonFormatter
import logging


def test_json_formatter():
    formatter = JsonFormatter()
    assert formatter is not None


def test_structured_logger():
    log = StructuredLogger("test")
    assert log is not None
    log.info("test message")
    log.warning("test warning")
