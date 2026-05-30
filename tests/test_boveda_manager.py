"""Tests for core/boveda_manager.py — Fernet-encrypted vault for secrets."""

import logging
from unittest.mock import MagicMock, patch

import pytest

logging.disable(logging.CRITICAL)


def _build_fernet_mock():
    f = MagicMock()
    f.encrypt.return_value = b"enc_token"
    f.decrypt.return_value = b"decrypted_value"
    return f


class TestImports:
    """Module imports cleanly."""

    def test_imports_without_error(self):
        from core.boveda_manager import guardar, recuperar, eliminar, listar, verificar_integridad

        assert callable(guardar)
        assert callable(recuperar)
        assert callable(eliminar)
        assert callable(listar)
        assert callable(verificar_integridad)


class TestGuardarRecuperar:
    """Encrypt and decrypt round-trip."""

    def test_guardar_and_recuperar_roundtrip(self):
        f = _build_fernet_mock()
        with (
            patch("core.boveda_manager._get_fernet", return_value=f),
            patch("core.boveda_manager._load_index", return_value={}),
            patch("core.boveda_manager._save_index"),
            patch("core.boveda_manager.CRYPTO_AVAILABLE", True),
        ):
            from core.boveda_manager import guardar, recuperar

            guardar("test_key", "my_secret")
        with (
            patch("core.boveda_manager._get_fernet", return_value=f),
            patch("core.boveda_manager._load_index", return_value={"test_key": "enc_token"}),
        ):
            from core.boveda_manager import recuperar

            result = recuperar("test_key")
        assert result == "decrypted_value"

    def test_recuperar_nonexistent_returns_none(self):
        f = _build_fernet_mock()
        with (
            patch("core.boveda_manager._get_fernet", return_value=f),
            patch("core.boveda_manager._load_index", return_value={}),
        ):
            from core.boveda_manager import recuperar

            result = recuperar("does_not_exist")
            assert result is None

    def test_recuperar_corrupt_returns_none(self):
        f = _build_fernet_mock()
        f.decrypt.side_effect = Exception("bad token")
        with (
            patch("core.boveda_manager._get_fernet", return_value=f),
            patch("core.boveda_manager._load_index", return_value={"bad": "corrupt"}),
        ):
            from core.boveda_manager import recuperar

            result = recuperar("bad")
            assert result is None


class TestEliminar:
    """Deletion from vault."""

    def test_eliminar_existing_returns_true(self):
        with (
            patch("core.boveda_manager._load_index", return_value={"key": "token"}),
            patch("core.boveda_manager._save_index"),
        ):
            from core.boveda_manager import eliminar

            result = eliminar("key")
            assert result is True

    def test_eliminar_nonexistent_returns_false(self):
        with (
            patch("core.boveda_manager._load_index", return_value={}),
            patch("core.boveda_manager._save_index"),
        ):
            from core.boveda_manager import eliminar

            result = eliminar("nope")
            assert result is False


class TestListar:
    """Listing secrets."""

    def test_listar_returns_list(self):
        with patch("core.boveda_manager._load_index", return_value={}):
            from core.boveda_manager import listar

            assert isinstance(listar(), list)


class TestNoCrypto:
    """Without cryptography installed."""

    def test_crypto_unavailable_raises(self):
        with patch("core.boveda_manager.CRYPTO_AVAILABLE", False):
            from core.boveda_manager import guardar

            with pytest.raises(RuntimeError, match="cryptography"):
                guardar("x", "y")
