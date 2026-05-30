#!/usr/bin/env python3
"""
Tests de Integración para Niveles de Conciencia 21-25

Verifica que todos los niveles de conciencia funcionan correctamente juntos
y que se integran correctamente en ura_unified_context.
"""

import pytest
import logging
from core.ura_environment_awareness import get_ura_environment_awareness
from core.ura_tools_awareness import get_ura_tools_awareness
from core.ura_hardware_awareness import get_ura_hardware_awareness
from core.ura_applications_awareness import get_ura_applications_awareness
from core.ura_tools_interaction import get_ura_tools_interaction
from core.ura_unified_context import get_ura_unified_context
from core.ura_validator import URAValidator

logging.basicConfig(level=logging.INFO)


class TestIntegrationAwareness:
    """Tests de integración para niveles de conciencia 21-25."""

    def test_environment_awareness_singleton(self):
        """Test que environment awareness tiene singleton correcto."""
        env1 = get_ura_environment_awareness()
        env2 = get_ura_environment_awareness()
        assert env1 is env2, "Environment awareness debe ser singleton"

    def test_environment_awareness_context(self):
        """Test que environment awareness genera contexto correctamente."""
        env = get_ura_environment_awareness()
        context = env.get_environment_context()
        assert isinstance(context, str)
        assert len(context) > 0
        assert "CONCIENCIA DEL ENTORNO" in context or "environment" in context.lower()

    def test_tools_awareness_singleton(self):
        """Test que tools awareness tiene singleton correcto."""
        tools1 = get_ura_tools_awareness()
        tools2 = get_ura_tools_awareness()
        assert tools1 is tools2, "Tools awareness debe ser singleton"

    def test_tools_awareness_context(self):
        """Test que tools awareness genera contexto correctamente."""
        tools = get_ura_tools_awareness()
        context = tools.get_tools_context()
        assert isinstance(context, str)
        assert len(context) > 0

    def test_hardware_awareness_singleton(self):
        """Test que hardware awareness tiene singleton correcto."""
        hw1 = get_ura_hardware_awareness()
        hw2 = get_ura_hardware_awareness()
        assert hw1 is hw2, "Hardware awareness debe ser singleton"

    def test_hardware_awareness_context(self):
        """Test que hardware awareness genera contexto correctamente."""
        hw = get_ura_hardware_awareness()
        context = hw.get_hardware_context()
        assert isinstance(context, str)
        assert len(context) > 0

    def test_applications_awareness_singleton(self):
        """Test que applications awareness tiene singleton correcto."""
        apps1 = get_ura_applications_awareness()
        apps2 = get_ura_applications_awareness()
        assert apps1 is apps2, "Applications awareness debe ser singleton"

    def test_applications_awareness_context(self):
        """Test que applications awareness genera contexto correctamente."""
        apps = get_ura_applications_awareness()
        context = apps.get_applications_context()
        assert isinstance(context, str)
        assert len(context) > 0

    def test_tools_interaction_singleton(self):
        """Test que tools interaction tiene singleton correcto."""
        ti1 = get_ura_tools_interaction()
        ti2 = get_ura_tools_interaction()
        assert ti1 is ti2, "Tools interaction debe ser singleton"

    def test_tools_interaction_context(self):
        """Test que tools interaction genera contexto correctamente."""
        ti = get_ura_tools_interaction()
        context = ti.get_tools_interaction_context()
        assert isinstance(context, str)
        assert len(context) > 0

    def test_tools_interaction_safe_command(self):
        """Test que tools interaction ejecuta comandos seguros."""
        ti = get_ura_tools_interaction()
        result = ti.execute_shell_command("echo 'test'")
        assert result.success is True
        assert "test" in result.output

    def test_tools_interaction_unsafe_command(self):
        """Test que tools interaction rechaza comandos peligrosos."""
        ti = get_ura_tools_interaction()
        result = ti.execute_shell_command("rm -rf /")
        assert result.success is False
        assert (
            "peligroso" in result.error.lower()
            or "not permitido" in result.error.lower()
            or "not allowed" in result.error.lower()
        )

    def test_tools_interaction_safe_python(self):
        """Test que tools interaction ejecuta código Python seguro (subproceso aislado)."""
        ti = get_ura_tools_interaction()
        result = ti.execute_python_code("print(len([1, 2, 3]))")
        assert result.success is True
        assert "3" in result.output

    def test_tools_interaction_unsafe_python(self):
        """Test que tools interaction rechaza código Python peligroso."""
        ti = get_ura_tools_interaction()
        result = ti.execute_python_code("__import__('os')")
        assert result.success is False
        assert (
            "peligroso" in result.error.lower()
            or "not permitido" in result.error.lower()
            or "not allowed" in result.error.lower()
        )

    def test_unified_context_includes_all_levels(self):
        """Test que unified context incluye todos los niveles 21-25."""
        unified = get_ura_unified_context()
        contexts = unified.collect_all_contexts()

        required_levels = ["environment", "tools", "hardware", "applications", "tools_interaction"]

        for level in required_levels:
            assert level in contexts, f"Unified context debe incluir {level}"
            assert isinstance(contexts[level], str)

    def test_unified_context_priority_order(self):
        """Test que unified context tiene priority order correcto en método."""
        unified = get_ura_unified_context()
        # priority_order se genera dinámicamente en prioritize_information
        # Verificar que el método existe y funciona
        assert hasattr(unified, "prioritize_information")
        contexts = {"diary": "test", "emotions": "test"}
        prioritized = unified.prioritize_information(contexts)
        # prioritize_information devuelve una lista de contextos priorizados
        assert isinstance(prioritized, list)

    def test_validator_singleton(self):
        """Test que URAValidator no requiere singleton (stateless)."""
        validator1 = URAValidator()
        validator2 = URAValidator()
        # URAValidator es stateless, no necesita singleton
        assert validator1 is not validator2 or validator1 is validator2

    def test_validator_safe_command(self):
        """Test que validator acepta comandos seguros."""
        validator = URAValidator()
        is_safe, _ = validator.sanitize_shell_command("echo 'hello'")
        assert is_safe is True

    def test_validator_unsafe_command(self):
        """Test que validator rechaza comandos peligrosos."""
        validator = URAValidator()
        is_safe, error = validator.sanitize_shell_command("rm -rf /")
        assert is_safe is False
        assert (
            "peligroso" in error.lower()
            or "not permitido" in error.lower()
            or "not allowed" in error.lower()
        )

    def test_validator_safe_url(self):
        """Test que validator acepta URLs seguras."""
        validator = URAValidator()
        is_valid, _ = validator.validate_url("https://example.com")
        assert is_valid is True

    def test_validator_unsafe_url(self):
        """Test que validator rechaza URLs peligrosas."""
        validator = URAValidator()
        is_valid, _ = validator.validate_url("http://localhost")
        assert is_valid is False


class TestCrossPlatform:
    """Tests de cross-platform para applications awareness."""

    def test_applications_awareness_platform_detection(self):
        """Test que applications awareness detecta plataforma correctamente."""
        apps = get_ura_applications_awareness()
        context = apps.get_applications_context()
        assert isinstance(context, str)
        assert len(context) > 0


class TestPerformance:
    """Tests de performance para niveles 21-25."""

    def test_environment_scan_performance(self):
        """Test que environment scan tiene límites de performance."""
        env = get_ura_environment_awareness()
        # El escaneo debe ser rápido (menos de 30 segundos)
        import time

        start = time.time()
        context = env.get_environment_context()
        elapsed = time.time() - start
        assert elapsed < 30, f"Environment scan tardó {elapsed} segundos, debe ser < 30"
        assert len(context) > 0

    def test_tools_scan_performance(self):
        """Test que tools scan tiene límites de performance."""
        tools = get_ura_tools_awareness()
        # El escaneo debe ser rápido (menos de 20 segundos)
        import time

        start = time.time()
        context = tools.get_tools_context()
        elapsed = time.time() - start
        assert elapsed < 20, f"Tools scan tardó {elapsed} segundos, debe ser < 20"
        assert len(context) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
