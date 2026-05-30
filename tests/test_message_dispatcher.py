"""Tests for core/message_dispatcher.py — message routing and dispatch."""

import logging
from unittest.mock import MagicMock, patch

import pytest

logging.disable(logging.CRITICAL)


@pytest.fixture
def mock_context():
    """Mock of URAMainWindowFinal with minimal attributes."""
    ctx = MagicMock()
    ctx.__class__.__module__ = "main_final"
    ctx.user_input = MagicMock()
    ctx.rate_limiter = None
    ctx.cache = None
    ctx.semantic_memory = None
    ctx.dynamic_context = None
    ctx.terminal_gateway = None
    ctx.pending_ura_response = ""
    ctx.active_streaming_threads = []
    ctx.ollama_connector = MagicMock()
    ctx._last_user_message = None
    ctx._search_thread = None
    ctx._vision_thread = None
    return ctx


@pytest.fixture
def dispatcher(mock_context):
    with patch("core.message_dispatcher.config", MagicMock()):
        from core.message_dispatcher import MessageDispatcher

        return MessageDispatcher(mock_context)


class TestInstantiation:
    """MessageDispatcher se instancia sin errores."""

    def test_instantiates_with_mock_context(self, mock_context):
        with patch("core.message_dispatcher.config", MagicMock()):
            from core.message_dispatcher import MessageDispatcher

            disp = MessageDispatcher(mock_context)
            assert disp is not None
            assert disp.context is mock_context

    def test_context_reference_retained(self, dispatcher, mock_context):
        assert dispatcher.context is mock_context


class TestDispatch:
    """dispatch() — API pública principal."""

    def test_emtpy_message_does_not_raise(self, dispatcher, mock_context):
        dispatcher.dispatch(mensaje="")
        mock_context.chat_user.assert_not_called()

    def test_none_message_does_not_raise(self, dispatcher, mock_context):
        mock_context.user_input.text.return_value = ""
        dispatcher.dispatch(mensaje=None)
        mock_context.chat_user.assert_not_called()

    def test_blank_message_does_not_raise(self, dispatcher, mock_context):
        dispatcher.dispatch(mensaje="   ")
        mock_context.chat_user.assert_not_called()


class TestRateLimit:
    """_apply_rate_limit() — control de frecuencia."""

    def test_no_rate_limiter_returns_false(self, dispatcher, mock_context):
        mock_context.rate_limiter = None
        with patch.object(dispatcher, "_mf", return_value=None):
            import core.ura_config as cfg

            with patch.object(cfg.config, "rate_limiter_available", False):
                result = dispatcher._apply_rate_limit()
                assert result is False

    def test_blocks_when_limit_exceeded(self, dispatcher, mock_context):
        limiter = MagicMock()
        limiter.allow_request.return_value = False
        mock_context.rate_limiter = limiter
        with patch.object(dispatcher, "_mf", return_value=None):
            import core.ura_config as cfg

            with patch.object(cfg.config, "rate_limiter_available", True):
                result = dispatcher._apply_rate_limit()
                assert result is True
                mock_context.chat_alert.assert_called_once()

    def test_allows_when_under_limit(self, dispatcher, mock_context):
        limiter = MagicMock()
        limiter.allow_request.return_value = True
        mock_context.rate_limiter = limiter
        with patch.object(dispatcher, "_mf", return_value=None):
            import core.ura_config as cfg

            with patch.object(cfg.config, "rate_limiter_available", True):
                result = dispatcher._apply_rate_limit()
                assert result is False


class TestCheckCache:
    """_check_cache() — respuestas cacheadas."""

    def test_no_cache_returns_none(self, dispatcher, mock_context):
        mock_context.cache = None
        result = dispatcher._check_cache("hola")
        assert result is None

    def test_cache_miss_returns_none(self, dispatcher, mock_context):
        cache = MagicMock()
        cache.get.return_value = None
        mock_context.cache = cache
        import core.ura_config as cfg

        with patch.object(cfg.config, "cache_available", True):
            result = dispatcher._check_cache("hola")
            assert result is None

    def test_cache_hit_returns_response(self, dispatcher, mock_context):
        cache = MagicMock()
        cache.get.return_value = "respuesta cacheada"
        mock_context.cache = cache
        import core.ura_config as cfg

        with patch.object(cfg.config, "cache_available", True):
            result = dispatcher._check_cache("hola")
            assert result == "respuesta cacheada"
            mock_context.chat_ura.assert_called_once_with("respuesta cacheada")


class TestRouteToHandler:
    """_route_to_handler() — enrutamiento a handlers específicos."""

    def test_no_match_returns_false(self, dispatcher, mock_context):
        with (
            patch("core.message_dispatcher.is_visual_automation_command", return_value=False),
            patch("core.message_dispatcher.is_install_command", return_value=False),
            patch("core.message_dispatcher.is_screen_area_command", return_value=False),
            patch("core.message_dispatcher.is_manual_command", return_value=False),
            patch("core.message_dispatcher.is_app_command", return_value=False),
            patch("core.message_dispatcher.is_windsurf_command", return_value=False),
            patch.object(dispatcher, "_mf", return_value=None),
        ):
            import core.ura_config as cfg

            for attr in dir(cfg.config):
                if attr.endswith("_available"):
                    try:
                        setattr(cfg.config, attr, False)
                    except Exception:
                        pass
            result = dispatcher._route_to_handler("un mensaje cualquiera")
            assert result is False

    def test_install_command_routes_correctly(self, dispatcher, mock_context):
        with (
            patch("core.message_dispatcher.is_visual_automation_command", return_value=False),
            patch("core.message_dispatcher.is_install_command", return_value=True),
            patch("core.message_dispatcher.is_screen_area_command", return_value=False),
            patch("core.message_dispatcher.is_manual_command", return_value=False),
            patch("core.message_dispatcher.is_app_command", return_value=False),
            patch("core.message_dispatcher.is_windsurf_command", return_value=False),
            patch.object(dispatcher, "_mf", return_value=None),
        ):
            import core.ura_config as cfg

            cfg.config.sandbox_installer_available = True
            result = dispatcher._route_to_handler("instala numpy")
            assert result is True
            mock_context._handle_sandbox_install.assert_called_once()
