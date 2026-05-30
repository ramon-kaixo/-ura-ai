#!/usr/bin/env python3
"""
Tests unitarios para RAM Manager
"""

import sys
from pathlib import Path

# Agregar ruta al directorio padre para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest


from core.ram_manager import (
    RamSnapshot,
    pick_model_for_ram,
    THRESHOLD_SMALL_GB,
    THRESHOLD_TINY_GB,
    MODEL_SMALL,
    MODEL_TINY,
)


class TestRAMManager(unittest.TestCase):
    """Tests para funciones de RAM Manager"""

    def test_pick_model_high_ram(self):
        """Test de selección de modelo con RAM alta"""
        snapshot = RamSnapshot(
            free_gb=4.0,
            inactive_gb=4.0,
            active_gb=4.0,
            wired_gb=2.0,
            compressor_gb=1.0,
            swap_used_gb=0.5,
        )
        # available = 8.0 GB, should pick MODEL_SMALL (>= 7.0 GB)
        model = pick_model_for_ram(snapshot)
        self.assertEqual(model, MODEL_SMALL)

    def test_pick_model_low_ram(self):
        """Test de selección de modelo con RAM baja"""
        snapshot = RamSnapshot(
            free_gb=1.0,
            inactive_gb=2.0,
            active_gb=4.0,
            wired_gb=2.0,
            compressor_gb=1.0,
            swap_used_gb=0.5,
        )
        # available = 3.0 GB, should pick MODEL_TINY (< 3.5 GB)
        model = pick_model_for_ram(snapshot)
        self.assertEqual(model, MODEL_TINY)

    def test_pick_model_threshold_boundary(self):
        """Test de selección de modelo en el umbral"""
        # Exactly at threshold (7.0 GB)
        snapshot = RamSnapshot(
            free_gb=3.5,
            inactive_gb=3.5,
            active_gb=4.0,
            wired_gb=2.0,
            compressor_gb=1.0,
            swap_used_gb=0.5,
        )
        model = pick_model_for_ram(snapshot)
        self.assertEqual(model, MODEL_SMALL)

    def test_threshold_constants(self):
        """Test de constantes de umbral"""
        self.assertEqual(THRESHOLD_SMALL_GB, 7.0)
        self.assertEqual(THRESHOLD_TINY_GB, 3.5)


if __name__ == "__main__":
    unittest.main()
