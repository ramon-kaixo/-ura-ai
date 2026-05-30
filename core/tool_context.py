#!/usr/bin/env python3
"""
URA Tool Context - Context Manager Universal para Herramientas
Sistema para abrir, inicializar y gestionar herramientas con cleanup automático
"""

import importlib
import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from core.tool_registry import TOOL_REGISTRY, ToolSpec


# ============================================================
# CONTEXT MANAGER PARA HERRAMIENTAS
# ============================================================
class ToolContext:
    """Context manager universal para abrir y gestionar herramientas"""

    def __init__(self, tool_registry=None):
        self.registry = tool_registry or TOOL_REGISTRY
        self.active_tools: dict[str, Any] = {}
        self._check_dependencies_cache: dict[str, bool] = {}

    @contextmanager
    def open(self, tool_id: str) -> Generator[Any, None, None]:
        """
        Abrir herramienta con context manager

        Args:
            tool_id: ID de la herramienta (ej: "llm_ollama")

        Yields:
            Instancia de la herramienta inicializada

        Example:
            with TOOL_CONTEXT.open("llm_ollama") as ollama:
                response = ollama.generate("Hola")
        """
        spec = self.registry.get(tool_id)
        if not spec:
            raise ValueError(f"Herramienta {tool_id} no encontrada")

        if not spec["activo"]:
            raise ValueError(f"Herramienta {tool_id} está inactiva")

        # Verificar dependencias
        self._check_dependencies(spec["dependencias"])

        # Inicializar herramienta
        tool_instance = self._initialize_tool(spec)
        self.active_tools[tool_id] = tool_instance

        try:
            yield tool_instance
        finally:
            # Cleanup
            self._cleanup(tool_id, tool_instance)

    def _check_dependencies(self, deps: list[str]):
        """Verificar dependencias"""
        for dep in deps:
            if dep not in self._check_dependencies_cache:
                available = self._is_available(dep)
                self._check_dependencies_cache[dep] = available

            if not self._check_dependencies_cache[dep]:
                raise RuntimeError(f"Dependencia {dep} no disponible")

    def _is_available(self, dep: str) -> bool:
        """Verificar si dependencia está disponible"""
        # Verificar si es un paquete Python
        try:
            importlib.import_module(dep)
            return True
        except ImportError:
            pass

        # Verificar si es un servicio externo
        if dep == "ollama":
            return self._check_ollama()
        elif dep == "redis":
            return self._check_redis()
        elif dep == "postgresql":
            return self._check_postgresql()

        # Por defecto, asumir disponible
        return True

    def _check_ollama(self) -> bool:
        """Verificar si Ollama está disponible"""
        try:
            import requests

            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False

    def _check_redis(self) -> bool:
        """Verificar si Redis está disponible"""
        try:
            import redis

            r = redis.Redis(host="localhost", port=6379, decode_responses=True)
            r.ping()
            return True
        except:
            return False

    def _check_postgresql(self) -> bool:
        """Verificar si PostgreSQL está disponible"""
        try:
            import psycopg2

            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="ura_db",
                user="ura_user",
                password=os.getenv("POSTGRES_PASSWORD", ""),
            )
            conn.close()
            return True
        except:
            return False

    def _initialize_tool(self, spec: ToolSpec) -> Any:
        """Inicializar herramienta"""
        # Si la función es un placeholder, crear una instancia simulada
        if spec["funcion"]() is None:
            return self._create_mock_instance(spec)

        return spec["funcion"]()

    def _create_mock_instance(self, spec: ToolSpec) -> Any:
        """Crear instancia simulada de herramienta"""

        class MockTool:
            def __init__(self, spec):
                self.spec = spec
                self.category = spec["categoria"]
                self.name = spec["nombre"]

            def __repr__(self):
                return f"MockTool({self.name})"

            def execute(self, *args, **kwargs):
                return {"status": "mock", "tool": self.name}

        return MockTool(spec)

    def _cleanup(self, tool_id: str, instance: Any):
        """Limpiar recursos"""
        try:
            # Cerrar conexiones, liberar recursos, etc.
            if hasattr(instance, "close"):
                instance.close()
            elif hasattr(instance, "disconnect"):
                instance.disconnect()
        except Exception as e:
            print(f"Error limpiando herramienta {tool_id}: {e}")
        finally:
            if tool_id in self.active_tools:
                del self.active_tools[tool_id]

    def get_active_tools(self) -> list[str]:
        """Obtener lista de herramientas activas"""
        return list(self.active_tools.keys())

    def get_tool_instance(self, tool_id: str) -> Any | None:
        """Obtener instancia de herramienta activa"""
        return self.active_tools.get(tool_id)


# ============================================================
# CONFIGURATION MANAGER
# ============================================================
class ToolConfigManager:
    """Gestor de configuración de herramientas"""

    def __init__(self, tool_registry=None):
        self.registry = tool_registry or TOOL_REGISTRY
        self.configs: dict[str, dict] = {}

    def set_config(self, tool_id: str, config: dict):
        """Configurar herramienta"""
        spec = self.registry.get(tool_id)
        if not spec:
            raise ValueError(f"Herramienta {tool_id} no encontrada")

        # Validar configuración
        validated = self._validate_config(spec["config_schema"], config)
        self.configs[tool_id] = validated

    def get_config(self, tool_id: str) -> dict:
        """Obtener configuración"""
        spec = self.registry.get(tool_id)
        if not spec:
            return {}
        default = spec.get("config_default", {})
        return self.configs.get(tool_id, default)

    def _validate_config(self, schema: dict, config: dict) -> dict:
        """Validar configuración contra esquema"""
        validated = {}
        for key, value in config.items():
            if key in schema:
                field_schema = schema[key]
                field_type = field_schema.get("type")

                # Validar tipo
                if field_type == "string":
                    if not isinstance(value, str):
                        raise ValueError(f"{key} debe ser string")
                elif field_type == "int":
                    if not isinstance(value, int):
                        raise ValueError(f"{key} debe ser int")
                    # Validar rango
                    if "min" in field_schema and value < field_schema["min"]:
                        raise ValueError(f"{key} debe ser >= {field_schema['min']}")
                    if "max" in field_schema and value > field_schema["max"]:
                        raise ValueError(f"{key} debe ser <= {field_schema['max']}")
                elif field_type == "float":
                    if not isinstance(value, int | float):
                        raise ValueError(f"{key} debe ser float")
                    if "min" in field_schema and value < field_schema["min"]:
                        raise ValueError(f"{key} debe ser >= {field_schema['min']}")
                    if "max" in field_schema and value > field_schema["max"]:
                        raise ValueError(f"{key} debe ser <= {field_schema['max']}")

                validated[key] = value
            else:
                # Campo extra, ignorar o advertir
                pass

        return validated

    def reset_config(self, tool_id: str):
        """Resetear configuración a valores por defecto"""
        if tool_id in self.configs:
            del self.configs[tool_id]


# ============================================================
# METRICS MANAGER
# ============================================================
class ToolMetrics:
    """Gestor de métricas de herramientas"""

    def __init__(self):
        self.metrics: dict[str, dict] = {}

    def record(self, tool_id: str, metric_name: str, value: float):
        """Registrar métrica"""
        if tool_id not in self.metrics:
            self.metrics[tool_id] = {}
        if metric_name not in self.metrics[tool_id]:
            self.metrics[tool_id][metric_name] = []

        from datetime import datetime

        self.metrics[tool_id][metric_name].append(
            {"value": value, "timestamp": datetime.now().isoformat()}
        )

    def get_stats(self, tool_id: str, metric_name: str) -> dict:
        """Obtener estadísticas de métrica"""
        values = self.metrics.get(tool_id, {}).get(metric_name, [])
        if not values:
            return {}

        nums = [v["value"] for v in values]
        return {
            "count": len(nums),
            "avg": sum(nums) / len(nums),
            "min": min(nums),
            "max": max(nums),
        }

    def get_all_metrics(self, tool_id: str) -> dict:
        """Obtener todas las métricas de una herramienta"""
        return self.metrics.get(tool_id, {})


# Instancias globales
TOOL_CONTEXT = ToolContext()
TOOL_CONFIG = ToolConfigManager()
TOOL_METRICS = ToolMetrics()

# Test
if __name__ == "__main__":
    print("=" * 50)
    print("URA Tool Context - Test")
    print("=" * 50)

    # Test abrir herramienta
    try:
        with TOOL_CONTEXT.open("llm_ollama") as ollama:
            print(f"✅ Herramienta abierta: {ollama}")
            print(f"   Categoría: {ollama.category}")
            print(f"   Nombre: {ollama.name}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test herramientas activas
    print(f"\n🔧 Herramientas activas: {TOOL_CONTEXT.get_active_tools()}")

    # Test configuración
    TOOL_CONFIG.set_config("llm_ollama", {"model": "gemma3:1b", "temperature": 0.7})
    config = TOOL_CONFIG.get_config("llm_ollama")
    print(f"\n⚙️ Configuración llm_ollama: {config}")

    # Test métricas
    TOOL_METRICS.record("llm_ollama", "latency", 0.5)
    TOOL_METRICS.record("llm_ollama", "latency", 0.6)
    TOOL_METRICS.record("llm_ollama", "latency", 0.4)
    stats = TOOL_METRICS.get_stats("llm_ollama", "latency")
    print(f"\n📊 Métricas llm_ollama/latency: {stats}")

    print("\n✅ Tool Context OK")
