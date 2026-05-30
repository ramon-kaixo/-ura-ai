#!/usr/bin/env python3
"""
tests/test_error_auto_repair.py - Tests unitarios del sistema de auto-reparación
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.error_auto_repair import ErrorAutoRepair


class TestErrorAutoRepair(unittest.TestCase):
    """Tests del sistema de auto-reparación"""

    def setUp(self):
        """Configuración antes de cada test"""
        # Crear directorio temporal para tests
        self.temp_dir = tempfile.mkdtemp()  # nosec B108

        # Crear instancia de ErrorAutoRepair con directorios temporales
        self.repair_system = ErrorAutoRepair.__new__(ErrorAutoRepair)
        self.repair_system.repair_history_file = Path(self.temp_dir) / "repair_history.json"
        self.repair_system.config_file = Path(self.temp_dir) / "config.json"
        self.repair_system.rollback_file = Path(self.temp_dir) / "rollback.json"
        self.repair_system._ensure_directories()
        self.repair_system._load_config()

    def tearDown(self):
        """Limpieza después de cada test"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_error_type(self):
        """Test detección de tipo de error"""
        test_cases = [
            ("ModuleNotFoundError: No module named 'requests'", "missing_module"),
            ("Permission denied", "permission"),
            ("Connection timeout", "connection"),
            ("Ollama not responding", "ollama"),
            ("Redis connection error", "redis"),
            ("File not found", "missing_file"),
            ("Import error", "import_error"),
            ("KeyError: 'test'", "key_error"),
            ("AttributeError: 'NoneType' object has no attribute", "attribute_error"),
            ("TypeError: unsupported operand type", "type_error"),
            ("Unknown error", "unknown"),
        ]

        for error_message, expected_type in test_cases:
            with self.subTest(error_message=error_message):
                detected_type = ErrorAutoRepair.detect_error_type(error_message)
                self.assertEqual(detected_type, expected_type)

    def test_save_and_load_history(self):
        """Test guardar y cargar historial"""
        # Guardar entrada de prueba
        test_entry = {
            "timestamp": "2026-04-28T12:00:00",
            "error_type": "missing_module",
            "error_message": "No module named 'test'",
            "success": True,
            "repair_message": "Módulo instalado",
        }

        history = [test_entry]

        with open(self.repair_system.repair_history_file, "w") as f:
            json.dump(history, f)

        # Cargar historial
        loaded_history = self.repair_system.get_repair_history()

        self.assertEqual(len(loaded_history), 1)
        self.assertEqual(loaded_history[0]["error_type"], "missing_module")

    def test_get_recurrent_errors(self):
        """Test detección de errores recurrentes"""
        # Crear historial con errores recurrentes
        history = [
            {"error_type": "missing_module", "success": False, "timestamp": "2026-04-28T12:00:00"},
            {"error_type": "missing_module", "success": False, "timestamp": "2026-04-28T13:00:00"},
            {"error_type": "missing_module", "success": False, "timestamp": "2026-04-28T14:00:00"},
            {"error_type": "ollama", "success": True, "timestamp": "2026-04-28T15:00:00"},
        ]

        with open(self.repair_system.repair_history_file, "w") as f:
            json.dump(history, f)

        # Obtener errores recurrentes
        recurrent = self.repair_system.get_recurrent_errors()

        self.assertEqual(recurrent.get("missing_module"), 3)
        self.assertNotIn("ollama", recurrent)  # Ollama fue exitoso, no recurrente

    def test_get_error_priority(self):
        """Test obtención de prioridad de error"""
        # Test errores críticos
        critical_errors = ["ollama", "redis"]
        for error in critical_errors:
            priority = self.repair_system.get_error_priority(error)
            self.assertEqual(priority, "critical")

        # Test errores de alta prioridad
        high_errors = ["missing_module", "import_error"]
        for error in high_errors:
            priority = self.repair_system.get_error_priority(error)
            self.assertEqual(priority, "high")

        # Test error desconocido
        priority = self.repair_system.get_error_priority("unknown")
        self.assertEqual(priority, "low")

    def test_priority_order(self):
        """Test ordenamiento por prioridad"""
        errors = ["missing_module", "ollama", "key_error", "redis"]

        ordered = self.repair_system.get_priority_order(errors)

        # Debe ser: ollama, redis (critical), missing_module (high), key_error (low)
        self.assertEqual(ordered[0], "ollama")
        self.assertEqual(ordered[1], "redis")
        self.assertEqual(ordered[2], "missing_module")
        self.assertEqual(ordered[3], "key_error")

    def test_config_persistence(self):
        """Test persistencia de configuración"""
        # Modificar configuración
        self.repair_system.config["auto_repair_enabled"] = False
        self.repair_system.config["test_key"] = "test_value"
        self.repair_system._save_config()

        # Crear nueva instancia y cargar configuración
        new_system = ErrorAutoRepair.__new__(ErrorAutoRepair)
        new_system.config_file = self.repair_system.config_file
        new_system._load_config()

        self.assertEqual(new_system.config["auto_repair_enabled"], False)
        self.assertEqual(new_system.config["test_key"], "test_value")


if __name__ == "__main__":
    unittest.main()
