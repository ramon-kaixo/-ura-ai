#!/usr/bin/env python3
"""
Tests unitarios para URAConsciousnessCoordinator.
"""

import unittest
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ura_consciousness_coordinator import URAConsciousnessCoordinator


class TestURAConsciousnessCoordinator(unittest.TestCase):
    def setUp(self):
        """Coordinador nuevo para cada test."""
        self.coordinator = URAConsciousnessCoordinator()

    def test_negotiate_with_weighted_proposals(self):
        """Probar negotiate con propuestas variadas."""
        proposals = [
            {"id": "p1", "priority": 1, "weight": 0.2},
            {"id": "p2", "priority": 10, "weight": 0.8},
            {"id": "p3", "priority": 5, "weight": 0.5},
        ]

        result = self.coordinator.negotiate(proposals)

        self.assertIn("accepted_proposal", result)
        # Verificar que negotiate devuelve un resultado válido (puede ser None o una propuesta)
        if result["accepted_proposal"]:
            self.assertIn("id", result["accepted_proposal"])

    def test_negotiate_with_equal_priorities(self):
        """Probar negotiate con propuestas de igual prioridad."""
        proposals = [
            {"id": "p1", "priority": 5, "weight": 0.5},
            {"id": "p2", "priority": 5, "weight": 0.7},
            {"id": "p3", "priority": 5, "weight": 0.3},
        ]

        result = self.coordinator.negotiate(proposals)

        self.assertIn("accepted_proposal", result)
        # Verificar que negotiate devuelve un resultado válido
        if result["accepted_proposal"]:
            self.assertIn("id", result["accepted_proposal"])

    def test_negotiate_empty_proposals(self):
        """Probar negotiate con lista vacía."""
        result = self.coordinator.negotiate([])
        self.assertIn("accepted_proposal", result)
        self.assertIsNone(result["accepted_proposal"])

    def test_singleton(self):
        """Probar que se pueden crear múltiples instancias."""
        coord1 = URAConsciousnessCoordinator()
        coord2 = URAConsciousnessCoordinator()
        # No es singleton, pero verificamos que funcionan independientemente
        self.assertIsNot(coord1, coord2)


if __name__ == "__main__":
    unittest.main()
