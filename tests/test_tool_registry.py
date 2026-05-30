#!/usr/bin/env python3
"""
Tests para Tool Registry
"""

import sys
from pathlib import Path

import pytest

# Agregar path al proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.tool_registry import TOOL_REGISTRY, ToolCategory, ToolRegistry


class TestToolRegistry:
    """Tests para ToolRegistry"""

    def test_registry_initialization(self):
        """Test inicialización del registro"""
        assert TOOL_REGISTRY is not None
        assert len(TOOL_REGISTRY.tools) > 0

    def test_register_tool(self):
        """Test registrar herramienta"""
        registry = ToolRegistry()

        spec = {
            "nombre": "test_tool",
            "categoria": ToolCategory.LLM,
            "descripcion": "Herramienta de prueba",
            "funcion": lambda: None,
            "input_schema": {},
            "output_schema": {},
            "dependencias": [],
            "uso_concurrente_max": 1,
            "prioridad": 5,
            "activo": True,
            "version": "1.0.0",
            "autor": "test",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": [],
            "tags": [],
            "vocabulario": {},
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": [],
            "referencias": [],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": False,
            "metrics_to_track": [],
            "cache_enabled": False,
            "cache_ttl": 0,
            "required_permissions": [],
            "allowed_roles": [],
        }

        tool_id = registry.register(spec)
        assert tool_id == "llm_test_tool"
        assert "llm_test_tool" in registry.tools

    def test_get_tool(self):
        """Test obtener herramienta"""
        spec = TOOL_REGISTRY.get("llm_ollama")
        assert spec is not None
        assert spec["nombre"] == "ollama"
        assert spec["categoria"] == ToolCategory.LLM

    def test_get_nonexistent_tool(self):
        """Test obtener herramienta inexistente"""
        spec = TOOL_REGISTRY.get("nonexistent")
        assert spec is None

    def test_list_by_category(self):
        """Test listar herramientas por categoría"""
        llm_tools = TOOL_REGISTRY.list_by_category(ToolCategory.LLM)
        assert len(llm_tools) > 0

        for tool in llm_tools:
            assert tool["categoria"] == ToolCategory.LLM

    def test_get_available_tools(self):
        """Test obtener herramientas activas"""
        available = TOOL_REGISTRY.get_available_tools()
        assert len(available) > 0

        # Verificar que todas estén activas
        for tool_id in available:
            spec = TOOL_REGISTRY.get(tool_id)
            assert spec["activo"]

    def test_deactivate_tool(self):
        """Test desactivar herramienta"""
        registry = ToolRegistry()

        spec = {
            "nombre": "deactivate_test",
            "categoria": ToolCategory.LLM,
            "descripcion": "Test deactivate",
            "funcion": lambda: None,
            "input_schema": {},
            "output_schema": {},
            "dependencias": [],
            "uso_concurrente_max": 1,
            "prioridad": 5,
            "activo": True,
            "version": "1.0.0",
            "autor": "test",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": [],
            "tags": [],
            "vocabulario": {},
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": [],
            "referencias": [],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": False,
            "metrics_to_track": [],
            "cache_enabled": False,
            "cache_ttl": 0,
            "required_permissions": [],
            "allowed_roles": [],
        }

        tool_id = registry.register(spec)
        assert tool_id in registry.get_available_tools()

        registry.deactivate(tool_id)
        assert tool_id not in registry.get_available_tools()

    def test_activate_tool(self):
        """Test activar herramienta"""
        registry = ToolRegistry()

        spec = {
            "nombre": "activate_test",
            "categoria": ToolCategory.LLM,
            "descripcion": "Test activate",
            "funcion": lambda: None,
            "input_schema": {},
            "output_schema": {},
            "dependencias": [],
            "uso_concurrente_max": 1,
            "prioridad": 5,
            "activo": False,
            "version": "1.0.0",
            "autor": "test",
            "fecha_creacion": "2026-04-27",
            "fecha_actualizacion": "2026-04-27",
            "changelog": [],
            "tags": [],
            "vocabulario": {},
            "test_function": None,
            "test_data": None,
            "ejemplos_uso": [],
            "notas": [],
            "referencias": [],
            "config_schema": {},
            "config_default": {},
            "metrics_enabled": False,
            "metrics_to_track": [],
            "cache_enabled": False,
            "cache_ttl": 0,
            "required_permissions": [],
            "allowed_roles": [],
        }

        tool_id = registry.register(spec)
        assert tool_id not in registry.get_available_tools()

        registry.activate(tool_id)
        assert tool_id in registry.get_available_tools()

    def test_find_tools_by_tag(self):
        """Test encontrar herramientas por tag"""
        tools = TOOL_REGISTRY.find_tools_by_tag("stable")
        assert len(tools) > 0

        for tool in tools:
            assert "stable" in tool["tags"]

    def test_get_stats(self):
        """Test obtener estadísticas"""
        stats = TOOL_REGISTRY.get_stats()

        assert "total" in stats
        assert "activas" in stats
        assert "inactivas" in stats
        assert "por_categoria" in stats

        assert stats["total"] > 0
        assert stats["activas"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
