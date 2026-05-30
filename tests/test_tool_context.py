#!/usr/bin/env python3
"""
Tests para Tool Context
"""

import sys
from pathlib import Path

import pytest

# Agregar path al proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.tool_context import TOOL_CONTEXT


class TestToolContext:
    """Tests para ToolContext"""

    def test_context_initialization(self):
        """Test inicialización del context"""
        assert TOOL_CONTEXT is not None
        assert TOOL_CONTEXT.registry is not None

    def test_open_tool(self):
        """Test abrir herramienta"""
        try:
            with TOOL_CONTEXT.open("llm_ollama") as tool:
                assert tool is not None
                assert hasattr(tool, "name")
                assert tool.name == "ollama"
        except Exception as e:
            # Puede fallar si Ollama no está disponible, pero el context debe funcionar
            assert "mock" in str(e).lower() or "dependencia" in str(e).lower()

    def test_open_nonexistent_tool(self):
        """Test abrir herramienta inexistente"""
        with pytest.raises(ValueError, match="no encontrada"):
            with TOOL_CONTEXT.open("nonexistent_tool"):
                pass

    def test_get_active_tools(self):
        """Test obtener herramientas activas"""
        active = TOOL_CONTEXT.get_active_tools()
        assert isinstance(active, list)

    def test_get_tool_instance(self):
        """Test obtener instancia de herramienta"""
        instance = TOOL_CONTEXT.get_tool_instance("llm_ollama")
        # Puede ser None si no está abierta
        assert instance is None or hasattr(instance, "name")


class TestToolConfigManager:
    """Tests para ToolConfigManager"""

    def test_config_initialization(self):
        """Test inicialización del config manager"""
        from core.tool_context import TOOL_CONFIG

        assert TOOL_CONFIG is not None

    def test_set_config(self):
        """Test establecer configuración"""
        from core.tool_context import TOOL_CONFIG

        TOOL_CONFIG.set_config("llm_ollama", {"model": "gemma3:1b", "temperature": 0.7})
        config = TOOL_CONFIG.get_config("llm_ollama")

        assert config["model"] == "gemma3:1b"
        assert config["temperature"] == 0.7

    def test_get_default_config(self):
        """Test obtener configuración por defecto"""
        from core.tool_context import TOOL_CONFIG

        config = TOOL_CONFIG.get_config("llm_ollama")
        assert "model" in config
        assert config["model"] == "gemma3:1b"

    def test_reset_config(self):
        """Test resetear configuración"""
        from core.tool_context import TOOL_CONFIG

        TOOL_CONFIG.set_config("llm_ollama", {"model": "custom"})
        TOOL_CONFIG.reset_config("llm_ollama")

        config = TOOL_CONFIG.get_config("llm_ollama")
        assert config["model"] == "gemma3:1b"  # Default

    def test_config_validation(self):
        """Test validación de configuración"""
        from core.tool_context import TOOL_CONFIG

        # Temperatura fuera de rango
        with pytest.raises(ValueError, match="debe ser"):
            TOOL_CONFIG.set_config("llm_ollama", {"temperature": 3.0})


class TestToolMetrics:
    """Tests para ToolMetrics"""

    def test_metrics_initialization(self):
        """Test inicialización del metrics manager"""
        from core.tool_context import TOOL_METRICS

        assert TOOL_METRICS is not None

    def test_record_metric(self):
        """Test registrar métrica"""
        from core.tool_context import TOOL_METRICS

        TOOL_METRICS.record("llm_ollama", "latency", 0.5)
        TOOL_METRICS.record("llm_ollama", "latency", 0.6)

        stats = TOOL_METRICS.get_stats("llm_ollama", "latency")

        assert stats["count"] == 2
        assert stats["avg"] == 0.55

    def test_get_stats_empty(self):
        """Test obtener estadísticas de métrica vacía"""
        from core.tool_context import TOOL_METRICS

        stats = TOOL_METRICS.get_stats("nonexistent", "latency")
        assert stats == {}

    def test_get_all_metrics(self):
        """Test obtener todas las métricas"""
        from core.tool_context import TOOL_METRICS

        TOOL_METRICS.record("llm_ollama", "latency", 0.5)
        TOOL_METRICS.record("llm_ollama", "success_rate", 1.0)

        all_metrics = TOOL_METRICS.get_all_metrics("llm_ollama")

        assert "latency" in all_metrics
        assert "success_rate" in all_metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
