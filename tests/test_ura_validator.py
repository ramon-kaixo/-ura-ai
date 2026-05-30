#!/usr/bin/env python3
"""
Tests para URAValidator
Validación y sanitización de entradas para seguridad
"""

import pytest
from core.ura_validator import URAValidator


class TestURAValidator:
    """Tests para URAValidator."""

    @pytest.fixture
    def validator(self):
        """Fixture para URAValidator."""
        return URAValidator()

    def test_sanitize_shell_command_safe(self, validator):
        """Test sanitización de comando seguro."""
        is_safe, result = validator.sanitize_shell_command("echo 'hello'")
        assert is_safe is True
        assert result == "echo 'hello'"

    def test_sanitize_shell_command_dangerous(self, validator):
        """Test sanitización de comando peligroso."""
        is_safe, result = validator.sanitize_shell_command("rm -rf /")
        assert is_safe is False
        assert "peligroso" in result.lower()

    def test_sanitize_shell_command_empty(self, validator):
        """Test sanitización de comando vacío."""
        is_safe, result = validator.sanitize_shell_command("")
        assert is_safe is False
        assert "vacío" in result.lower()

    def test_sanitize_shell_command_too_long(self, validator):
        """Test sanitización de comando demasiado largo."""
        long_command = "a" * 1001
        is_safe, result = validator.sanitize_shell_command(long_command)
        assert is_safe is False
        assert "largo" in result.lower()

    def test_sanitize_python_code_safe(self, validator):
        """Test sanitización de código Python seguro."""
        is_safe, result = validator.sanitize_python_code("print('hello')")
        assert is_safe is True
        assert result == "print('hello')"

    def test_sanitize_python_code_dangerous(self, validator):
        """Test sanitización de código Python peligroso."""
        is_safe, result = validator.sanitize_python_code("__import__('os')")
        assert is_safe is False
        assert "peligroso" in result.lower()

    def test_sanitize_python_code_empty(self, validator):
        """Test sanitización de código Python vacío."""
        is_safe, result = validator.sanitize_python_code("")
        assert is_safe is False
        assert "vacío" in result.lower()

    def test_validate_url_valid(self, validator):
        """Test validación de URL válida."""
        is_valid, result = validator.validate_url("https://example.com")
        assert is_valid is True
        assert result == "https://example.com"

    def test_validate_url_invalid_protocol(self, validator):
        """Test validación de URL con protocolo inválido."""
        is_valid, result = validator.validate_url("ftp://example.com")
        assert is_valid is False
        assert "no permitido" in result.lower()

    def test_validate_url_localhost(self, validator):
        """Test validación de URL localhost."""
        is_valid, result = validator.validate_url("http://localhost")
        assert is_valid is False
        assert "localhost" in result.lower()

    def test_validate_url_empty(self, validator):
        """Test validación de URL vacía."""
        is_valid, result = validator.validate_url("")
        assert is_valid is False
        assert "vacía" in result.lower()

    def test_validate_path_valid(self, validator):
        """Test validación de path válido."""
        is_valid, result = validator.validate_path("/home/user")
        assert is_valid is True
        assert result == "/home/user"

    def test_validate_path_traversal(self, validator):
        """Test validación de path con path traversal."""
        is_valid, result = validator.validate_path("../../etc/passwd")
        assert is_valid is False
        assert "traversal" in result.lower()

    def test_validate_path_empty(self, validator):
        """Test validación de path vacío."""
        is_valid, result = validator.validate_path("")
        assert is_valid is False
        assert "vacío" in result.lower()

    def test_validate_query_valid(self, validator):
        """Test validación de query válido."""
        is_valid, result = validator.validate_query("python async await")
        assert is_valid is True
        assert result == "python async await"

    def test_validate_query_sql_injection(self, validator):
        """Test validación de query con SQL injection."""
        is_valid, result = validator.validate_query("'; DROP TABLE users; --")
        assert is_valid is False
        assert "inyección" in result.lower()

    def test_validate_query_too_long(self, validator):
        """Test validación de query demasiado largo."""
        long_query = "a" * 501
        is_valid, result = validator.validate_query(long_query)
        assert is_valid is False
        assert "larg" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
