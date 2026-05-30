#!/usr/bin/env python3
"""
Agente Revisor de Rendimiento - URA App
Revisa rendimiento del código
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgenteRevisorRendimiento:
    """Revisa rendimiento del código"""

    def __init__(self):
        self.nombre = "agente_revisor_rendimiento"

    def revisar(self, codigo: str) -> dict:
        """Revisar rendimiento del código"""
        resultado = {"estado": "ok", "problemas": [], "optimizaciones": [], "sugerencias": []}

        # Verificar bucles anidados
        nested_loops = codigo.count("for ") + codigo.count("while ")
        if nested_loops > 2:
            resultado["problemas"].append(f"Muchos bucles anidados: {nested_loops}")

        # Verificar uso de list comprehension vs loops
        if "for " in codigo and "list(" in codigo:
            resultado["optimizaciones"].append("Considerar usar list comprehension")

        # Verificar uso de .append en loop
        if ".append(" in codigo and "for " in codigo:
            resultado["optimizaciones"].append(
                "Considerar usar list comprehension en lugar de .append"
            )

        # Verificar si hay caching
        if "cache" not in codigo.lower() and "@lru_cache" not in codigo:
            resultado["sugerencias"].append("Considerar agregar caching para funciones costosas")

        # Verificar si hay async
        if "async" not in codigo and "await" not in codigo:
            resultado["sugerencias"].append("Considerar usar async/await para operaciones I/O")

        return resultado


# Instancia global
agente_revisor_rendimiento = AgenteRevisorRendimiento()
