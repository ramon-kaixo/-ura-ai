"""Tests para core/utils/anonymizer.py."""


from core.utils.anonymizer import sanitize_text


class TestSanitizeText:
    def test_texto_vacio(self) -> None:
        assert sanitize_text("") == ""

    def test_texto_sin_sensibles(self) -> None:
        texto = "Hola mundo, esto es una prueba normal."
        assert sanitize_text(texto) == texto

    def test_ip_address(self) -> None:
        texto = "Servidor en 192.168.1.1 y backup en 10.0.0.1"
        resultado = sanitize_text(texto)
        assert "[IP_REDACTADA]" in resultado
        assert "192.168.1.1" not in resultado
        assert "10.0.0.1" not in resultado

    def test_system_path(self) -> None:
        texto = "Config en /home/ramon/.config/app/settings.json"
        resultado = sanitize_text(texto)
        assert "[RUTA_SISTEMA_REDACTADA]" in resultado
        assert "/home/ramon" not in resultado

    def test_generic_secret_password(self) -> None:
        texto = 'password = "secreto123"'
        resultado = sanitize_text(texto)
        assert 'password: "[CREDENTIAL_REDACTADA]"' in resultado
        assert "secreto123" not in resultado

    def test_generic_secret_api_key(self) -> None:
        texto = "api_key: 'abc-def-ghi'"
        resultado = sanitize_text(texto)
        assert 'api_key: "[CREDENTIAL_REDACTADA]"' in resultado
        assert "abc-def-ghi" not in resultado

    def test_openai_key(self) -> None:
        clave = "sk-" + "a" * 48
        texto = f"Mi clave es {clave} para OpenAI"
        resultado = sanitize_text(texto)
        assert "[OPENAI_API_KEY_REDACTADA]" in resultado
        assert clave not in resultado

    def test_anthropic_key(self) -> None:
        clave = "sk-ant-api03-" + "b" * 45
        texto = f"Clave Anthropic: {clave}"
        resultado = sanitize_text(texto)
        assert "[ANTHROPIC_API_KEY_REDACTADA]" in resultado
        assert clave not in resultado

    def test_ssh_private_key(self) -> None:
        clave = "-----BEGIN RSA PRIVATE KEY-----\nabc123\n-----END RSA PRIVATE KEY-----"
        texto = f"Mi clave SSH:\n{clave}"
        resultado = sanitize_text(texto)
        assert "[SSH_PRIVATE_KEY_REDACTADA]" in resultado
        assert "BEGIN RSA PRIVATE KEY" not in resultado

    def test_multiples_patrones(self) -> None:
        texto = 'IP: 192.168.1.1, password = "secret", path: /home/ramon/docs'
        resultado = sanitize_text(texto)
        assert "[IP_REDACTADA]" in resultado
        assert '[CREDENTIAL_REDACTADA]' in resultado
        assert "[RUTA_SISTEMA_REDACTADA]" in resultado
