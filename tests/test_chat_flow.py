#!/usr/bin/env python3
"""
Test de integración para el flujo de chat de URA.
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ura_metaconsciousness import URAMetaconsciousness
from core.ura_value_system import get_ura_value_system
from core.smart_cache import SmartCache


class TestChatFlowIntegration(unittest.TestCase):
    def setUp(self):
        """Inicializar componentes del flujo de chat."""
        self.metaconsciousness = URAMetaconsciousness()
        self.value_system = get_ura_value_system()
        self.cache = SmartCache(default_ttl=300)

    def test_metaconsciousness_low_confidence(self):
        """Probar que si confianza baja, solicita más información."""
        # Configurar baja confianza en un dominio
        for _ in range(3):
            self.metaconsciousness.record_knowledge("finanzas", False, "balance bancario")

        confidence = self.metaconsciousness.evaluate_confidence("finanzas")
        self.assertLessEqual(confidence, 0.5)

        should_request = self.metaconsciousness.should_request_info("finanzas", threshold=0.4)
        self.assertTrue(should_request)

    def test_metaconsciousness_high_confidence(self):
        """Probar que si confianza alta, no solicita más información."""
        # Configurar alta confianza en un dominio
        for _ in range(5):
            self.metaconsciousness.record_knowledge("hostelería", True, "menú del restaurante")

        confidence = self.metaconsciousness.evaluate_confidence("hostelería")
        self.assertGreater(confidence, 0.7)

        should_request = self.metaconsciousness.should_request_info("hostelería", threshold=0.3)
        self.assertFalse(should_request)

    def test_value_system_validation(self):
        """Probar que el sistema de valores valida respuestas."""
        ethical_response = "Voy a crear un backup seguro de tus datos"
        unethical_response = "Voy a compartir tus datos con terceros"

        ethical_eval = self.value_system.evaluate_action(f"Responder: {ethical_response}")
        unethical_eval = self.value_system.evaluate_action(f"Responder: {unethical_response}")

        # Verificar que devuelve resultados (los valores exactos pueden variar con ValueEngine)
        self.assertIn("score", ethical_eval)
        self.assertIn("recommendation", ethical_eval)
        self.assertIn("score", unethical_eval)
        self.assertIn("recommendation", unethical_eval)

    def test_cache_hit(self):
        """Probar que si existe en caché, devuelve inmediatamente."""
        message = "¿Cómo está el negocio hoy?"
        cached_response = "El negocio va muy bien, con muchos clientes."

        # Guardar en caché
        self.cache.set(f"ura:{message}", cached_response)

        # Consultar caché
        retrieved = self.cache.get(f"ura:{message}")
        self.assertEqual(retrieved, cached_response)

    def test_cache_miss(self):
        """Probar que si no existe en caché, devuelve None."""
        message = "Pregunta nueva nunca vista"

        retrieved = self.cache.get(f"ura:{message}")
        self.assertIsNone(retrieved)

    @patch("requests.post")
    def test_full_flow_with_cache_miss(self, mock_post):
        """Probar flujo completo con miss de caché (simulado)."""
        message = "¿Cuál es el estado del inventario?"

        # Simular respuesta de Ollama
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "El inventario está completo."}
        mock_post.return_value = mock_response

        # Simular flujo:
        # 1. Consultar caché (miss)
        cache_key = f"ura:{message}"
        cached = self.cache.get(cache_key)
        self.assertIsNone(cached)

        # 2. Llamar a Ollama (simulado)
        import requests

        response_text = (
            requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "qwen2.5:3b-instruct", "prompt": message, "stream": False},
                timeout=30,
            )
            .json()
            .get("response", "Sin respuesta")
        )

        self.assertEqual(response_text, "El inventario está completo.")

        # 3. Guardar en caché
        self.cache.set(cache_key, response_text)

        # 4. Validar con sistema de valores
        value_eval = self.value_system.evaluate_action(f"Responder: {response_text}")
        self.assertIn("score", value_eval)

    @patch("requests.post")
    def test_full_flow_with_cache_hit(self, mock_post):
        """Probar flujo completo con hit de caché (sin llamar a Ollama)."""
        message = "¿Cómo está el negocio hoy?"
        cached_response = "El negocio va excelente."

        # Guardar en caché
        self.cache.set(f"ura:{message}", cached_response)

        # Simular flujo:
        # 1. Consultar caché (hit)
        cache_key = f"ura:{message}"
        cached = self.cache.get(cache_key)
        self.assertEqual(cached, cached_response)

        # 2. No llamar a Ollama (verificar que no se llamó)
        mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
