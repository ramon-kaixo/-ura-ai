#!/usr/bin/env python3
"""
Tests unitarios para Privacy Scrubber
"""

import sys
from pathlib import Path

# Agregar ruta al directorio padre para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

from core.privacy_scrubber import PrivacyScrubber


class TestPrivacyScrubber(unittest.TestCase):
    """Tests para PrivacyScrubber"""

    def setUp(self):
        """Configuración inicial de tests"""
        self.scrubber = PrivacyScrubber(username="test_user")

    def test_scrub_username(self):
        """Test de sanitización de nombre de usuario"""
        text = "Usuario test_user accedió al sistema"
        scrubbed, applied = self.scrubber.scrub_text(text)
        self.assertTrue(applied)
        self.assertNotIn("test_user", scrubbed)

    def test_scrub_password(self):
        """Test de sanitización de contraseñas"""
        text = "password=secreto123"
        scrubbed, applied = self.scrubber.scrub_text(text)
        self.assertTrue(applied)
        self.assertNotIn("secreto123", scrubbed)

    def test_scrub_email(self):
        """Test de sanitización de emails"""
        text = "Contacta a test@example.com"
        scrubbed, applied = self.scrubber.scrub_text(text)
        self.assertTrue(applied)
        self.assertNotIn("test@example.com", scrubbed)

    def test_scrub_phone(self):
        """Test de sanitización de teléfonos"""
        text = "Llama al 123-456-7890"
        scrubbed, applied = self.scrubber.scrub_text(text)
        self.assertTrue(applied)
        self.assertNotIn("123-456-7890", scrubbed)

    def test_no_sensitive_data(self):
        """Test de texto sin datos sensibles"""
        text = "Este texto no tiene datos sensibles"
        scrubbed, applied = self.scrubber.scrub_text(text)
        self.assertFalse(applied)
        self.assertEqual(text, scrubbed)


if __name__ == "__main__":
    unittest.main()
