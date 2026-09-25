import pytest
"""Tests de json_logger."""

from motor.observability.logging import JSONFormatter, StructuredLogger


@pytest.mark.unit
def test_json_formatter() -> None:
    formatter = JSONFormatter()
    assert formatter is not None


@pytest.mark.unit
def test_structured_logger() -> None:
    log = StructuredLogger("test")
    assert log is not None
    log.info("test message")
    log.warning("test warning")
