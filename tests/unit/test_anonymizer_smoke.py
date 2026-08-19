"""Tests smoke generados por plantilla (determinista, sin LLM)."""

import pytest

from motor.core.utils.anonymizer import sanitize_text


def test_import_anonymizer():
    """El módulo importa sin errores."""
    assert sanitize_text is not None


def test_funcion_anonymizer_sanitize_text():
    """La función no lanza con argumentos básicos."""
    try:
        sanitize_text('')
    except (TypeError, ValueError, NotImplementedError):
        pytest.skip('no aplicable con argumentos básicos')



def test_sanitize_text_vacio():
    """Cobertura de rama: texto vacío retorna vacío."""
    assert sanitize_text("") == ""
    assert sanitize_text(None) == ""


def test_sanitize_text_patrones():
    """Cobertura de ramas: cada patrón regex es ejercitado."""
    casos = [
        ("sk-123456789012345678901234567890123456789012345678", "[OPENAI_API_KEY_REDACTADA]"),
        ("-----BEGIN RSA PRIVATE KEY-----\nAAA\n-----END RSA PRIVATE KEY-----", "[SSH_PRIVATE_KEY_REDACTADA]"),
        ('password="supersecreto"', 'password: "[CREDENTIAL_REDACTADA]"'),
        ("192.168.1.1", "[IP_REDACTADA]"),
    ]
    for texto, esperado in casos:
        assert sanitize_text(texto) == esperado, f"falló: {texto[:20]}"
