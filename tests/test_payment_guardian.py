"""Tests for core/payment_guardian.py — tiered payment authorization."""

import logging
from unittest.mock import patch

import pytest

logging.disable(logging.CRITICAL)


@pytest.fixture(autouse=True)
def mock_deps():
    """Prevent external dependencies."""
    with patch("core.payment_guardian._show_qt_dialog", return_value=(True, "ok")):
        with patch("core.payment_guardian._qt_disponible", return_value=True):
            with patch("core.payment_guardian._send_telegram_buttons"):
                with patch("core.payment_guardian._audit"):
                    yield


class TestAutorizarPago:
    """autorizar_pago() — umbrales <10e, 10-49e, >=100e."""

    def test_small_amount_auto_approved(self):
        from core.payment_guardian import autorizar_pago

        result = autorizar_pago(5.0, "cafe")
        assert result is True

    def test_medium_amount_notifies(self):
        from core.payment_guardian import autorizar_pago

        result = autorizar_pago(25.0, "licencia")
        assert result is True

    def test_large_amount_blocked(self):
        from core.payment_guardian import autorizar_pago

        result = autorizar_pago(150.0, "servidor")
        assert result is False

    def test_exactly_100_blocked(self):
        from core.payment_guardian import autorizar_pago

        result = autorizar_pago(100.0, "hardware")
        assert result is False

    def test_returns_bool(self):
        from core.payment_guardian import autorizar_pago

        result = autorizar_pago(1.0, "test")
        assert isinstance(result, bool)
