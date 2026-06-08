"""Test del anonymizer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.utils.anonymizer import sanitize_text

def test_anonymizer_simple():
    raw = """
    config = {
        "api_key": "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmn_vanguardia",
        "root_path": "/home/ramon/URA/ura_ia_1972/config",
        "node_ip": "100.123.81.101"
    }
    """
    s = sanitize_text(raw)
    assert "sk-ant" not in s, f"API key filtrada: {s}"
    assert "/home/ramon" not in s, f"Ruta filtrada: {s}"
    assert "100.123.81.101" not in s, f"IP filtrada: {s}"
    assert "[ANTHROPIC_API_KEY_REDACTADA]" in s
    assert "[RUTA_SISTEMA_REDACTADA]" in s
    assert "[IP_REDACTADA]" in s
    print("  ✅ test_anonymizer_simple PASS")

def test_anonymizer_openai():
    raw = 'key = "sk-abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmn"'
    s = sanitize_text(raw)
    assert "[OPENAI_API_KEY_REDACTADA]" in s
    print("  ✅ test_anonymizer_openai PASS")

def test_anonymizer_ssh():
    raw = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0gM
-----END RSA PRIVATE KEY-----"""
    s = sanitize_text(raw)
    assert "[SSH_PRIVATE_KEY_REDACTADA]" in s
    print("  ✅ test_anonymizer_ssh PASS")

def test_anonymizer_credential():
    raw = 'password = "supersecreto"'
    s = sanitize_text(raw)
    assert "[CREDENTIAL_REDACTADA]" in s
    assert "supersecreto" not in s
    print("  ✅ test_anonymizer_credential PASS")

def test_anonymizer_empty():
    assert sanitize_text("") == ""
    assert sanitize_text(None) == ""  # type: ignore
    print("  ✅ test_anonymizer_empty PASS")

if __name__ == "__main__":
    test_anonymizer_simple()
    test_anonymizer_openai()
    test_anonymizer_ssh()
    test_anonymizer_credential()
    test_anonymizer_empty()
    print("\n  ✅ Todos los tests del anonymizer pasaron")
