#!/usr/bin/env python3
"""
Módulo: core/code_agents/tools/install_tools.py
Propósito: Verifica e instala dependencias del sistema (pip, brew, apt).
Dependencias principales: subprocess, logging, json
Reglas especiales: SOLO leer comandos. No ejecutar con privilegios elevados. Capturar todos los errores.
"""

import subprocess
import sys


def install_tool(tool: str) -> bool:
    """Instalar herramienta"""
    try:
        print(f"Instalando {tool}...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", tool], check=True, capture_output=True
        )
        print(f"✅ {tool} instalado exitosamente")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error instalando {tool}: {e}")
        return False


def verify_installation(tool: str) -> bool:
    """Verificar instalación"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", tool, "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(f"✅ {tool} verificado: {result.stdout.strip()}")
            return True
        return False
    except Exception:
        return False


def main():
    """Instalar todas las herramientas"""
    tools = ["black", "isort", "ruff", "mypy", "bandit", "pylint"]

    print("=== INSTALANDO HERRAMIENTAS AUTOMÁTICAS ===\n")

    # Instalar herramientas
    for tool in tools:
        install_tool(tool)

    print("\n=== VERIFICANDO INSTALACIONES ===\n")

    # Verificar instalaciones
    for tool in tools:
        verify_installation(tool)

    print("\n=== INSTALACIÓN COMPLETADA ===")


if __name__ == "__main__":
    main()
