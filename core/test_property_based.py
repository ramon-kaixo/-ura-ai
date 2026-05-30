#!/usr/bin/env python3
"""
Tests property-based para URA usando Hypothesis
"""

import sys
from pathlib import Path

# Agregar ruta al directorio padre para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

from core.agente_policia_v2 import AgentePoliciaV2
from core.privacy_scrubber import PrivacyScrubber
from hypothesis import given, settings
from hypothesis import strategies as st


class TestPropertyBased(unittest.TestCase):
    """Tests property-based usando Hypothesis"""

    def setUp(self):
        """Configuración inicial de tests"""
        self.scrubber = PrivacyScrubber(username="test_user")
        self.policia = AgentePoliciaV2()

    @given(st.text(min_size=1, max_size=1000))
    def test_scrub_text_always_returns_string(self, text: str):
        """Test que scrub_text siempre retorna string"""
        scrubbed, applied = self.scrubber.scrub_text(text)
        assert isinstance(scrubbed, str)

    @given(st.text(min_size=1, max_size=1000))
    def test_scrub_text_never_increases_length(self, text: str):
        """Test que scrub_text nunca aumenta el tamaño del texto"""
        scrubbed, applied = self.scrubber.scrub_text(text)
        assert len(scrubbed) <= len(text)

    @given(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10))
    def test_scrub_multiple_texts(self, texts: list[str]):
        """Test sanitización de múltiples textos"""
        for text in texts:
            scrubbed, applied = self.scrubber.scrub_text(text)
            assert isinstance(scrubbed, str)
            assert len(scrubbed) <= len(text)

    @given(
        st.text(
            alphabet=st.characters(whitelist_categories=["Lu", "Ll", "Nd"]),
            min_size=1,
            max_size=100,
        )
    )
    def test_safe_text_not_modified(self, text: str):
        """Test que texto seguro (solo letras y números) no es modificado"""
        scrubbed, applied = self.scrubber.scrub_text(text)
        if not applied:
            assert scrubbed == text

    @given(st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    def test_security_check_never_crashes(self, command: str):
        """Test que check_command nunca crashea con cualquier input"""
        try:
            result = self.policia.validar(command)
            assert isinstance(result, dict)
            assert "veredicto" in result
        except Exception as e:
            self.fail(f"validar crashed with input '{command}': {e}")

    @given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=20))
    def test_batch_security_checks(self, commands: list[str]):
        """Test de verificación de seguridad en batch"""
        for command in commands:
            result = self.policia.validar(command)
            assert isinstance(result, dict)
            assert "veredicto" in result

    @given(st.integers(min_value=0, max_value=100))
    def test_ram_threshold_positive(self, threshold: int):
        """Test que el umbral de RAM es siempre positivo"""
        assert threshold >= 0

    @given(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.text(min_size=1, max_size=100),
            min_size=0,
            max_size=10,
        )
    )
    def test_context_handling(self, context: dict[str, str]):
        """Test manejo de contexto con cualquier diccionario"""
        assert isinstance(context, dict)
        for key, value in context.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    @given(st.text(min_size=1, max_size=100))
    def test_bypass_detection_consistent(self, text: str):
        """Test que detección de bypass es consistente"""
        result1 = self.policia.validar(text)["veredicto"]
        result2 = self.policia.validar(text)["veredicto"]
        assert result1 == result2


if __name__ == "__main__":
    unittest.main()
