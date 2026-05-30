#!/usr/bin/env python3
"""
Agente Optimizador Móvil - URA App
Optimiza cualquier código
"""


class AgenteOptimizador:
    """Agente optimizador"""

    def __init__(self):
        self.nombre = "agente_optimizador"
        self.box_actual = None

    def asignar_box(self, box: str):
        """Asignar agente a un box específico"""
        self.box_actual = box

    def optimizar_codigo(self, codigo: str) -> str:
        """Optimizar código"""
        # Eliminar líneas vacías múltiples
        lineas = [linea for linea in codigo.split("\n") if linea.strip()]
        return "\n".join(lineas)


# Instancia global
agente_optimizador = AgenteOptimizador()
