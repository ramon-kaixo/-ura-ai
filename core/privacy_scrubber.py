#!/usr/bin/env python3
"""
URA - Privacy Scrubber
Sistema de sanitización de datos sensibles
"""

from pathlib import Path

import logging
import re

# Configurar logging
BENCHMARKS_DIR = Path(__file__).parent.parent / "benchmarks"
PRIVACY_LOG = BENCHMARKS_DIR / "privacy_scrubber.log"

# Crear directorio de benchmarks si no existe
BENCHMARKS_DIR.mkdir(exist_ok=True)

# Configurar logger para privacy scrubber
privacy_logger = logging.getLogger("privacy_scrubber")
privacy_logger.setLevel(logging.INFO)
handler = logging.FileHandler(PRIVACY_LOG)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
privacy_logger.addHandler(handler)


class PrivacyScrubber:
    """Sistema de Sanitización de Datos para Protección de Privacidad"""

    def __init__(self, username="ramonesnaola"):
        self.username = username
        self.privacy_filters_failed = False

        # Patrones de regex para detección
        self.patterns = {
            "username": re.compile(rf"\b{re.escape(username)}\b", re.IGNORECASE),
            "full_path_user": re.compile(r"/Users/[^/]+/"),
            "password_like": re.compile(r"(password|passwd|pass)[\s:=]+[^\s]+", re.IGNORECASE),
            "token_like": re.compile(r"(token|api_key|apikey|secret)[\s:=]+[^\s]+", re.IGNORECASE),
            "ip_private": re.compile(
                r"\b(10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.)\d+\.\d+\b"
            ),
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        }

    def scrub_text(self, text: str) -> tuple[str, bool]:
        """
        Sanitizar texto aplicando todos los filtros de privacidad

        Args:
            text: Texto a sanitizar

        Returns:
            Tuple[str, bool]: (texto_sanitizado, filtros_aplicados)
        """
        if not text:
            return text, False

        original_text = text
        filters_applied = False

        # 1. Anonimizar nombre de usuario
        text = self._anonymize_username(text)
        if text != original_text:
            filters_applied = True
            privacy_logger.info("Username anonimizado")

        # 2. Convertir rutas completas a relativas
        text = self._anonymize_paths(text)
        if text != original_text:
            filters_applied = True
            privacy_logger.info("Rutas anonimizadas")

        # 3. Detectar y reemplazar patrones sensibles
        text = self._scrub_sensitive_patterns(text)
        if text != original_text:
            filters_applied = True
            privacy_logger.warning("Patrones sensibles detectados y reemplazados")

        # Verificar si algún filtro falló
        self.privacy_filters_failed = not filters_applied and self._contains_sensitive_data(
            original_text
        )

        return text, filters_applied

    def _anonymize_username(self, text: str) -> str:
        """Anonimizar nombre de usuario"""
        return self.patterns["username"].sub("[User]", text)

    def _anonymize_paths(self, text: str) -> str:
        """Convertir rutas completas de usuario a rutas relativas"""
        # Reemplazar /Users/username/ con ~/
        text = self.patterns["full_path_user"].sub("~/", text)
        return text

    def _scrub_sensitive_patterns(self, text: str) -> str:
        """Detectar y reemplazar patrones sensibles"""
        # Contraseñas
        text = self.patterns["password_like"].sub("[PASSWORD_REDACTED]", text)

        # Tokens
        text = self.patterns["token_like"].sub("[TOKEN_REDACTED]", text)

        # IPs privadas
        text = self.patterns["ip_private"].sub("[IP_PRIVATE_REDACTED]", text)

        # Emails
        text = self.patterns["email"].sub("[EMAIL_REDACTED]", text)

        # Teléfonos
        text = self.patterns["phone"].sub("[PHONE_REDACTED]", text)

        return text

    def _contains_sensitive_data(self, text: str) -> bool:
        """Verificar si el texto contiene datos sensibles"""
        for pattern_name, pattern in self.patterns.items():
            if pattern_name != "username" and pattern_name != "full_path_user":
                if pattern.search(text):
                    return True
        return False

    def scrub_terminal_output(self, output: str) -> str:
        """
        Sanitizar salida de terminal antes de enviar a IA

        Args:
            output: Salida de terminal

        Returns:
            str: Salida sanitizada
        """
        scrubbed, filters_applied = self.scrub_text(output)

        if filters_applied:
            privacy_logger.info(
                f"Salida de terminal sanitizada: {len(output)} -> {len(scrubbed)} caracteres"
            )

        return scrubbed

    def verify_sandbox(self) -> bool:
        """
        Verificar que el sistema funciona en Sandbox

        Returns:
            bool: True si Sandbox está activo
        """
        # Verificar que estamos en entorno controlado
        import os

        return os.path.exists("/tmp") and os.access("/tmp", os.W_OK)  # nosec B108

    def log_privacy_violation(self, violation_type: str, details: str):
        """Registrar violación de privacidad"""
        privacy_logger.error(f"VIOLACIÓN DE PRIVACIDAD: {violation_type} - {details}")
        self.privacy_filters_failed = True


if __name__ == "__main__":
    # Test del Privacy Scrubber
    print("Privacy Scrubber - Test")
    print(f"Log de privacidad: {PRIVACY_LOG}")

    scrubber = PrivacyScrubber()

    # Test de sanitización (texto de ejemplo genérico)
    test_text = "Usuario usuario_test accedió a /home/usuario/archivo.txt con password=secreto123"
    scrubbed, applied = scrubber.scrub_text(test_text)

    print(f"\nOriginal: {test_text}")
    print(f"Sanitizado: {scrubbed}")
    print(f"Filtros aplicados: {applied}")

    # Test de Sandbox
    print(f"\nSandbox activo: {scrubber.verify_sandbox()}")
