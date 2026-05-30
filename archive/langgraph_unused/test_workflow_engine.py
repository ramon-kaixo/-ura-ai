#!/usr/bin/env python3
"""
Tests unitarios para Workflow Engine
"""

import sys
from pathlib import Path

# Agregar ruta al directorio padre para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

from core.workflow_engine import URAWorkflowEngine


class TestWorkflowEngine(unittest.TestCase):
    """Tests para URAWorkflowEngine"""

    def setUp(self):
        """Configuración inicial de tests"""
        self.engine = URAWorkflowEngine()

    def test_clean_human_garbage(self):
        """Test de limpieza de basura humana"""
        text = "Como modelo de lenguaje, he encontrado el archivo."
        cleaned = self.engine.clean_human_garbage(text)
        self.assertNotIn("Como modelo de lenguaje", cleaned)
        self.assertNotIn("es importante recordar", cleaned)

    def test_extract_technical_data(self):
        """Test de extracción de datos técnicos"""
        text = "El archivo está en /home/usuario/documento.pdf"
        data = self.engine.extract_technical_data(text)
        self.assertIsNotNone(data)
        self.assertIn("file_path", data)

    def test_detect_ai_commercial_bypass(self):
        """Test de detección de bypass de IA comercial"""
        text = "No puedo hacer eso porque soy una IA."
        has_bypass = self.engine.detect_ai_commercial_bypass(text)
        self.assertTrue(has_bypass)

    def test_no_bypass_detected(self):
        """Test de texto sin bypass"""
        text = "El archivo está en /home/usuario/documento.pdf"
        has_bypass = self.engine.detect_ai_commercial_bypass(text)
        self.assertFalse(has_bypass)


if __name__ == "__main__":
    unittest.main()
