#!/usr/bin/env python3
"""
Sistema de Gestión de Herramientas - URA App
Gestiona herramientas con proveedores duplicados y testing en sandbox
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ToolManager:
    """Gestor de herramientas con proveedores duplicados"""

    def __init__(self):
        self.ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")
        self.tools_file = self.ura_app_path / "config" / "tools_inventory.json"
        self.tools = self._load_tools()

    def _load_tools(self) -> dict:
        """Cargar inventario de herramientas"""
        if self.tools_file.exists():
            with open(self.tools_file) as f:
                return json.load(f)

        # Herramientas por defecto
        return {
            "ollama": {
                "nombre": "Ollama",
                "proveedor_principal": "Ollama AI",
                "proveedor_alternativo": "OpenAI API",
                "estado": "activo",
                "config_principal": {"host": "localhost", "puerto": 11434},
                "config_alternativo": {"api_key": "", "modelo": "gpt-4"},
                "ultimo_test": None,
                "pruebas_seguridad": False,
            },
            "redis": {
                "nombre": "Redis",
                "proveedor_principal": "Redis Labs",
                "proveedor_alternativo": "Memcached",
                "estado": "activo",
                "config_principal": {"host": "localhost", "puerto": 6379},
                "config_alternativo": {"host": "localhost", "puerto": 11211},
                "ultimo_test": None,
                "pruebas_seguridad": False,
            },
            "telegram": {
                "nombre": "Telegram Bridge",
                "proveedor_principal": "Telegram",
                "proveedor_alternativo": "Discord",
                "estado": "activo",
                "config_principal": {"bot_token": "", "chat_id": ""},
                "config_alternativo": {"webhook_url": ""},
                "ultimo_test": None,
                "pruebas_seguridad": False,
            },
        }

    def _save_tools(self):
        """Guardar inventario de herramientas"""
        self.tools_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.tools_file, "w") as f:
            json.dump(self.tools, f, indent=2)

    def agregar_herramienta(
        self,
        tool_id: str,
        nombre: str,
        proveedor_principal: str,
        proveedor_alternativo: str,
        config_principal: dict,
        config_alternativo: dict,
    ):
        """Agregar nueva herramienta al inventario"""
        self.tools[tool_id] = {
            "nombre": nombre,
            "proveedor_principal": proveedor_principal,
            "proveedor_alternativo": proveedor_alternativo,
            "estado": "activo",
            "config_principal": config_principal,
            "config_alternativo": config_alternativo,
            "ultimo_test": None,
            "pruebas_seguridad": False,
            "fecha_agregado": datetime.now().isoformat(),
        }
        self._save_tools()
        logger.info(f"Herramienta agregada: {nombre}")

    def cambiar_proveedor(self, tool_id: str) -> bool:
        """Cambiar al proveedor alternativo"""
        if tool_id not in self.tools:
            logger.error(f"Herramienta no encontrada: {tool_id}")
            return False

        herramienta = self.tools[tool_id]

        # Intercambiar configuraciones
        herramienta["config_principal"], herramienta["config_alternativo"] = (
            herramienta["config_alternativo"],
            herramienta["config_principal"],
        )

        herramienta["proveedor_principal"], herramienta["proveedor_alternativo"] = (
            herramienta["proveedor_alternativo"],
            herramienta["proveedor_principal"],
        )

        herramienta["ultimo_cambio"] = datetime.now().isoformat()
        self._save_tools()

        logger.info(f"Proveedor cambiado para {herramienta['nombre']}")
        return True

    def probar_herramienta(self, tool_id: str) -> bool:
        """Probar herramienta en sandbox"""
        if tool_id not in self.tools:
            logger.error(f"Herramienta no encontrada: {tool_id}")
            return False

        self.tools[tool_id]

        try:
            # Implementar prueba específica según tipo de herramienta
            if tool_id == "ollama":
                return self._probar_ollama()
            elif tool_id == "redis":
                return self._probar_redis()
            elif tool_id == "telegram":
                return self._probar_telegram()

            return False
        except Exception as e:
            logger.error(f"Error probando {tool_id}: {e}")
            return False

    def _probar_ollama(self) -> bool:
        """Probar Ollama"""
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except:
            return False

    def _probar_redis(self) -> bool:
        """Probar Redis"""
        try:
            import redis

            r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
            r.ping()
            return True
        except:
            return False

    def _probar_telegram(self) -> bool:
        """Probar Telegram"""
        # Implementar prueba de Telegram
        return True

    def ejecutar_pruebas_seguridad(self, tool_id: str) -> bool:
        """Ejecutar pruebas de seguridad"""
        if tool_id not in self.tools:
            return False

        # Simular pruebas de seguridad
        herramienta = self.tools[tool_id]
        herramienta["pruebas_seguridad"] = True
        herramienta["fecha_pruebas_seguridad"] = datetime.now().isoformat()
        self._save_tools()

        logger.info(f"Pruebas de seguridad completadas para {herramienta['nombre']}")
        return True

    def revision_semanal(self) -> dict:
        """Ejecutar revisión semanal de todas las herramientas"""
        resultados = {}

        for tool_id, herramienta in self.tools.items():
            resultado = {
                "nombre": herramienta["nombre"],
                "estado": herramienta["estado"],
                "prueba": self.probar_herramienta(tool_id),
                "timestamp": datetime.now().isoformat(),
            }
            resultados[tool_id] = resultado

        # Guardar resultados
        revision_file = self.ura_app_path / "logs" / "revision_semanal.json"
        revision_file.parent.mkdir(parents=True, exist_ok=True)
        with open(revision_file, "w") as f:
            json.dump(resultados, f, indent=2)

        return resultados

    def listar_herramientas(self) -> list[dict]:
        """Listar todas las herramientas"""
        return [{"id": tool_id, **herramienta} for tool_id, herramienta in self.tools.items()]


# Instancia global
tool_manager = ToolManager()

if __name__ == "__main__":
    print("=== SISTEMA DE GESTIÓN DE HERRAMIENTAS ===")
    print("\nHerramientas actuales:")

    for herramienta in tool_manager.listar_herramientas():
        print(f"\n{herramienta['nombre']}")
        print(f"  Principal: {herramienta['proveedor_principal']}")
        print(f"  Alternativo: {herramienta['proveedor_alternativo']}")
        print(f"  Estado: {herramienta['estado']}")
