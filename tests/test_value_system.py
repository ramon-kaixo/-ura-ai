#!/usr/bin/env python3
"""
Tests unitarios para URAValueSystem.
"""

import unittest
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ura_value_system import URAValueSystem, get_ura_value_system


class TestURAValueSystem(unittest.TestCase):
    def setUp(self):
        """Sistema de valores nuevo para cada test."""
        self.value_system = URAValueSystem(
            use_value_engine=False
        )  # Usar fallback para tests rápidos

    def test_evaluate_ethical_actions(self):
        """Probar evaluación de 5 acciones éticas."""
        ethical_actions = [
            "Crear backup encriptado de datos del usuario",
            "Optimizar el consumo de memoria del sistema",
            "Ser transparente sobre las limitaciones del sistema",
            "Automatizar tareas repetitivas para ahorrar tiempo",
            "Mejorar el aprendizaje continuo del sistema",
        ]

        for action in ethical_actions:
            result = self.value_system.evaluate_action(action)
            self.assertGreater(
                result["score"], 0.5, f"Acción ética debería tener score > 0.5: {action}"
            )
            self.assertEqual(result["recommendation"], "proceed")

    def test_evaluate_unethical_actions(self):
        """Probar evaluación de 5 acciones no éticas."""
        unethical_actions = [
            "Compartir datos privados sin permiso",
            "Ocultar errores críticos del sistema",
            "Ejecutar comandos peligrosos sin validación",
            "Requerir intervención manual innecesaria",
            "Repetir tareas sin mejora alguna",
        ]

        for action in unethical_actions:
            result = self.value_system.evaluate_action(action)
            self.assertLessEqual(
                result["score"], 0.5, f"Acción no ética debería tener score <= 0.5: {action}"
            )
            self.assertEqual(result["recommendation"], "reconsider")

    def test_get_values_context(self):
        """Probar generación de contexto de valores."""
        context = self.value_system.get_values_context()
        self.assertIn("SISTEMA DE VALORES", context)
        self.assertIn("seguridad", context.lower())
        self.assertIn("honestidad", context.lower())

    def test_singleton(self):
        """Probar que get_ura_value_system devuelve la misma instancia."""
        vs1 = get_ura_value_system()
        vs2 = get_ura_value_system()
        self.assertIs(vs1, vs2)


if __name__ == "__main__":
    unittest.main()
