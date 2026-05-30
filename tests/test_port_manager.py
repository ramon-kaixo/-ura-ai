#!/usr/bin/env python3
"""
tests/test_port_manager.py - Tests del Sistema de Gestión de Puertos
Tests unitarios para port_manager.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.port_manager import PortManager


class TestPortManager(unittest.TestCase):
    """Tests del gestor de puertos"""

    def setUp(self):
        """Configuración antes de cada test"""
        # Crear archivo de configuración temporal
        self.temp_dir = tempfile.mkdtemp()  # nosec B108
        self.config_file = Path(self.temp_dir) / "ports_config.json"

        config_data = {
            "port_manager": {
                "enabled": True,
                "auto_assign": True,
                "port_range": {"start": 5000, "end": 5999},
                "reserved_ports": {"test_service": 5555, "another_service": 5556},
                "check_on_startup": True,
                "conflict_resolution": "skip",
            }
        }

        with open(self.config_file, "w") as f:
            json.dump(config_data, f)

        self.port_manager = PortManager(str(self.config_file))

    def tearDown(self):
        """Limpieza después de cada test"""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_config(self):
        """Test cargar configuración"""
        self.assertIsNotNone(self.port_manager.config)
        self.assertTrue(self.port_manager.config["port_manager"]["enabled"])

    def test_get_port_for_reserved_service(self):
        """Test obtener puerto para servicio reservado"""
        port = self.port_manager.get_port_for_service("test_service")
        self.assertEqual(port, 5555)

    def test_get_port_for_unknown_service(self):
        """Test obtener puerto para servicio desconocido"""
        # Debería asignar automáticamente un puerto
        port = self.port_manager.get_port_for_service("unknown_service")
        self.assertGreaterEqual(port, 5000)
        self.assertLessEqual(port, 5999)

    def test_is_port_available(self):
        """Test verificar disponibilidad de puerto"""
        # Puerto 5555 probablemente está libre en entorno de test
        available = self.port_manager.is_port_available(5555)
        self.assertTrue(available)

    def test_check_all_reserved_ports(self):
        """Test verificar todos los puertos reservados"""
        status = self.port_manager.check_all_reserved_ports()
        self.assertIn("test_service", status)
        self.assertIn("another_service", status)

    def test_get_assigned_ports(self):
        """Test obtener puertos asignados"""
        self.port_manager.get_port_for_service("test_service")
        assigned = self.port_manager.get_assigned_ports()
        self.assertIn("test_service", assigned)

    def test_detect_conflicts(self):
        """Test detección de conflictos"""
        conflicts = self.port_manager.detect_all_conflicts()
        self.assertIsInstance(conflicts, dict)

    def test_get_port_statistics(self):
        """Test obtener estadísticas"""
        stats = self.port_manager.get_port_statistics()
        self.assertIn("total_assigned", stats)
        self.assertIn("total_reserved", stats)
        self.assertIn("conflicts", stats)

    def test_port_history(self):
        """Test historial de puertos"""
        self.port_manager.get_port_for_service("test_service")
        history = self.port_manager.port_usage_history
        self.assertIn("test_service", history)


class TestFileLock(unittest.TestCase):
    """Tests del sistema de locks para archivos"""

    def setUp(self):
        """Configuración antes de cada test"""
        self.temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.temp_file.close()

    def tearDown(self):
        """Limpieza después de cada test"""
        Path(self.temp_file.name).unlink()

    def test_file_lock_basic(self):
        """Test básico de lock de archivo"""
        from core.file_lock import FileLock

        with FileLock(self.temp_file.name), open(self.temp_file.name, "w") as f:
            f.write('{"test": "data"}')

        with open(self.temp_file.name) as f:
            data = json.load(f)

        self.assertEqual(data["test"], "data")

    def test_safe_json_file(self):
        """Test de archivo JSON seguro"""
        from core.file_lock import SafeJSONFile

        safe_file = SafeJSONFile(self.temp_file.name, default={})

        # Test escritura
        safe_file.write({"key": "value"})
        data = safe_file.read()
        self.assertEqual(data["key"], "value")

        # Test actualización
        safe_file.update({"key2": "value2"})
        data = safe_file.read()
        self.assertEqual(data["key2"], "value2")


if __name__ == "__main__":
    unittest.main()
