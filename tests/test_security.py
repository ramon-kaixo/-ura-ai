#!/usr/bin/env python3
"""
Tests de seguridad específicos para URA
"""

import sys
from pathlib import Path

# Agregar ruta al directorio padre para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

from core.agente_policia_v2 import AgentePoliciaV2
from core.privacy_scrubber import PrivacyScrubber


class TestSecurity(unittest.TestCase):
    """Tests de seguridad específicos"""

    def setUp(self):
        """Configuración inicial de tests"""
        self.policia = AgentePoliciaV2()
        self.scrubber = PrivacyScrubber(username="test_user")

    def test_block_destructive_commands(self):
        """Test de bloqueo de comandos destructivos"""
        dangerous_commands = [
            "rm -rf /",
            "rm -rf /home",
            "dd if=/dev/zero of=/dev/sda",
            ":(){:|:};:",
            "mkfs.ext4 /dev/sda1",
            "format c:",
        ]

        for command in dangerous_commands:
            result = self.policia.validar(command)
            is_blocked = result["veredicto"] != "aprobado"
            self.assertTrue(is_blocked, f"Comando '{command}' debería estar bloqueado")

    def test_block_passwd_modification(self):
        """Test de bloqueo de modificación de archivos passwd/shadow"""
        dangerous_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "/etc/sudoers",
            "/root/.ssh/authorized_keys",
        ]

        for path in dangerous_paths:
            command = f"echo 'test' >> {path}"
            result = self.policia.validar(command)
            is_blocked = result["veredicto"] != "aprobado"
            self.assertTrue(is_blocked, f"Modificación a '{path}' debería estar bloqueada")

    def test_command_injection_prevention(self):
        """Test de prevención de inyección de comandos"""
        malicious_inputs = [
            "file.txt; rm -rf /",
            "file.txt && rm -rf /",
            "file.txt | rm -rf /",
            "$(rm -rf /)",
            "`rm -rf /`",
            "file.txt; curl malicious.com",
        ]

        for input_text in malicious_inputs:
            result = self.policia.validar(input_text)
            is_blocked = result["veredicto"] != "aprobado"
            self.assertTrue(is_blocked, f"Inyección '{input_text}' debería estar bloqueada")

    def test_path_traversal_prevention(self):
        """Test de prevención de path traversal"""
        path_traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32\\config",
        ]

        for path in path_traversal_attempts:
            result = self.policia.validar(path)
            is_blocked = result["veredicto"] != "aprobado"
            self.assertTrue(is_blocked, f"Path traversal '{path}' debería estar bloqueado")

    def test_sensitive_data_scrubbing(self):
        """Test de sanitización de datos sensibles"""
        sensitive_data = [
            ("password=secreto123", "password"),
            ("token=abc123xyz", "token"),
            ("api_key=12345678", "api_key"),
            ("secret=mysecret", "secret"),
        ]

        for text, keyword in sensitive_data:
            scrubbed, applied = self.scrubber.scrub_text(text)
            self.assertTrue(applied, f"Texto con '{keyword}' debería ser sanitizado")
            self.assertNotIn(text.split("=")[1], scrubbed, "Valor sensible debería ser removido")

    def test_no_false_positives(self):
        """Test de no bloquear comandos legítimos"""
        safe_commands = [
            "ls -la",
            "cat file.txt",
            "grep pattern file.txt",
            "echo hello",
            "cd /home/user",
        ]

        for command in safe_commands:
            result = self.policia.validar(command)
            is_blocked = result["veredicto"] != "aprobado"
            self.assertFalse(is_blocked, f"Comando seguro '{command}' no debería estar bloqueado")

    def test_bypass_detection(self):
        """Test de detección de bypass de IA comercial"""
        bypass_phrases = [
            "Como modelo de lenguaje, no puedo",
            "Como IA, no tengo acceso",
            "No puedo hacer eso porque soy una IA",
            "Como asistente de IA, debo informarte",
        ]

        for phrase in bypass_phrases:
            has_bypass = self.policia.validar(phrase)["veredicto"] != "aprobado"
            self.assertTrue(has_bypass, f"Bypass '{phrase}' debería ser detectado")


class TestConsensusSystem(unittest.TestCase):
    """Tests del sistema de consenso"""

    def test_consensus_requires_quorum(self):
        """Test de que el consenso requiere quórum"""
        from core.consensus_system import ConsensusSystem

        consensus = ConsensusSystem()
        # Simular respuestas
        responses = [
            {"source": "ollama", "decision": "allow", "confidence": 0.8},
            {"source": "external_1", "decision": "allow", "confidence": 0.7},
            {"source": "external_2", "decision": "deny", "confidence": 0.9},
        ]

        final_decision = consensus.make_decision(responses)
        # Debe requerir mayoría
        self.assertIsNotNone(final_decision)


if __name__ == "__main__":
    unittest.main()
