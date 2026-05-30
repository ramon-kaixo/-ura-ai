"""Tests for handlers/ — command handler modules."""

import logging
from unittest.mock import MagicMock

import pytest

logging.disable(logging.CRITICAL)


@pytest.fixture
def mock_context():
    """Mock of URAMainWindowFinal."""
    ctx = MagicMock()
    ctx.__class__.__module__ = "main_final"
    ctx.chat_ura = MagicMock()
    ctx.chat_alert = MagicMock()
    ctx.chat_user = MagicMock()
    ctx.hide_progress = MagicMock()
    ctx.user_input = MagicMock()
    ctx.user_input.text.return_value.text.return_value = ""
    return ctx


class TestVisionHandler:
    """handlers/vision_handler.py — screen area and visual automation."""

    def test_imports_without_error(self):
        from handlers.vision_handler import handle_screen_area, handle_visual_automation

        assert callable(handle_screen_area)
        assert callable(handle_visual_automation)

    def test_handle_screen_area_no_exception(self, mock_context):
        from handlers.vision_handler import handle_screen_area

        handle_screen_area(mock_context, "analiza esta pantalla")

    def test_handle_visual_automation_no_exception(self, mock_context):
        from handlers.vision_handler import handle_visual_automation

        handle_visual_automation(mock_context, "automatiza esto")


class TestAppHandler:
    """handlers/app_handler.py — macOS app commands."""

    def test_imports_without_error(self):
        from handlers.app_handler import handle_app_command

        assert callable(handle_app_command)

    def test_handle_app_no_exception(self, mock_context):
        from handlers.app_handler import handle_app_command

        handle_app_command(mock_context, "abre safari")


class TestManualHandler:
    """handlers/manual_handler.py — manual/documentation queries."""

    def test_imports_without_error(self):
        from handlers.manual_handler import handle_manual_query

        assert callable(handle_manual_query)

    def test_handle_manual_no_exception(self, mock_context):
        from handlers.manual_handler import handle_manual_query

        handle_manual_query(mock_context, "manual de python")


class TestInstallHandler:
    """handlers/install_handler.py — sandbox package installs."""

    def test_imports_without_error(self):
        from handlers.install_handler import handle_sandbox_install

        assert callable(handle_sandbox_install)

    def test_handle_install_no_exception(self, mock_context):
        from handlers.install_handler import handle_sandbox_install

        handle_sandbox_install(mock_context, "instala flask")


class TestWindsurfHandler:
    """handlers/windsurf_handler.py — Windsurf IDE integration."""

    def test_imports_without_error(self):
        from handlers.windsurf_handler import handle_windsurf_command

        assert callable(handle_windsurf_command)

    def test_handle_windsurf_no_exception(self, mock_context):
        from handlers.windsurf_handler import handle_windsurf_command

        handle_windsurf_command(mock_context, "windsurf crea test")
