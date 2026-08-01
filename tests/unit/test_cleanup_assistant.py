"""Tests for scripts/pro/cleanup_assistant.py."""
from unittest.mock import MagicMock, patch

from scripts.pro.cleanup_assistant import cleanup, main


class TestCleanup:
    @patch("scripts.pro.cleanup_assistant.MessageStore")
    def test_cleanup_returns_count(self, mock_store_class):
        mock_store = MagicMock()
        mock_store.cleanup_old.return_value = 42
        mock_store_class.return_value = mock_store

        result = cleanup(days=30)
        assert result == 42
        mock_store.cleanup_old.assert_called_once_with(days=30)

    @patch("scripts.pro.cleanup_assistant.MessageStore")
    def test_cleanup_different_days(self, mock_store_class):
        mock_store = MagicMock()
        mock_store.cleanup_old.return_value = 0
        mock_store_class.return_value = mock_store

        cleanup(days=7)
        mock_store.cleanup_old.assert_called_once_with(days=7)

    @patch("scripts.pro.cleanup_assistant.MessageStore")
    def test_cleanup_zero_days(self, mock_store_class):
        mock_store = MagicMock()
        mock_store.cleanup_old.return_value = 100
        mock_store_class.return_value = mock_store

        result = cleanup(days=0)
        assert result == 100


class TestMain:
    @patch("scripts.pro.cleanup_assistant.MessageStore")
    def test_main_prints(self, mock_store_class, capsys):
        mock_store = MagicMock()
        mock_store.cleanup_old.return_value = 42
        mock_store_class.return_value = mock_store

        main()
        captured = capsys.readouterr()
        assert "Limpieza completada: 42 mensajes antiguos eliminados" in captured.out

    @patch("scripts.pro.cleanup_assistant.MessageStore")
    def test_main_zero_deleted(self, mock_store_class, capsys):
        mock_store = MagicMock()
        mock_store.cleanup_old.return_value = 0
        mock_store_class.return_value = mock_store

        main()
        captured = capsys.readouterr()
        assert "Limpieza completada: 0 mensajes antiguos eliminados" in captured.out
