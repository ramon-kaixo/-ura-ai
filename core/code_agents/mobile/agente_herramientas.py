#!/usr/bin/env python3
"""
Agente Herramientas Móvil - URA App
Ejecuta herramientas automáticas (black, isort, ruff, mypy, bandit, pylint)
"""

import subprocess
import sys


class AgenteHerramientas:
    """Agente de herramientas automáticas"""

    def __init__(self):
        self.nombre = "agente_herramientas"
        self.box_actual = None

    def asignar_box(self, box: str):
        """Asignar agente a un box específico"""
        self.box_actual = box

    def ejecutar_herramientas(self, archivo: str) -> dict:
        """Ejecutar todas las herramientas en un archivo"""
        resultados = {}

        herramientas = ["black", "isort", "ruff", "mypy", "bandit", "pylint"]
        for herramienta in herramientas:
            try:
                subprocess.run(
                    [sys.executable, "-m", herramienta, archivo],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                resultados[herramienta] = "ok"
            except:
                resultados[herramienta] = "error"

        return resultados


# Instancia global
agente_herramientas = AgenteHerramientas()
