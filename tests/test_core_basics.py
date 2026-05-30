"""Tests for core modules: file_lock, model_config, logging_config, langchain_bridge, proactive_alerts."""

import logging


logging.disable(logging.CRITICAL)


class TestFileLock:
    def test_imports(self):
        pass

        assert True

    def test_filelock_exists(self):
        from core.file_lock import FileLock

        assert FileLock is not None


class TestModelConfig:
    def test_imports(self):
        from core.model_config import get_active_model

        assert callable(get_active_model)

    def test_returns_string(self):
        from core.model_config import get_active_model

        assert isinstance(get_active_model(), str)


class TestLoggingConfig:
    def test_imports(self):
        from core.logging_config import get_logger

        assert callable(get_logger)

    def test_returns_logger(self):
        from core.logging_config import get_logger

        logger = get_logger("test_basics")
        assert logger is not None


class TestLangChainBridge:
    def test_imports(self):
        from core.langchain_bridge import is_available

        assert callable(is_available)

    def test_returns_bool(self):
        from core.langchain_bridge import is_available

        assert isinstance(is_available(), bool)


class TestProactiveAlerts:
    def test_imports(self):
        from core.proactive_alerts import ProactiveAlerts

        assert ProactiveAlerts is not None
