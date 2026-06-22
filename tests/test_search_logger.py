"""Tests de search_logger."""

from core.search_logger import log_query, read_logs


def test_logger_imports() -> None:
    assert callable(log_query)
    assert callable(read_logs)
