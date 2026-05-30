#!/usr/bin/env python3
"""
Agente Revisor de Compatibilidad - URA App
Verifica compatibilidad del código
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgenteRevisorCompatibilidad:
    """Verifica compatibilidad del código"""

    def __init__(self):
        self.nombre = "agente_revisor_compatibilidad"
        self.python_version = "3.12"

    def revisar(self, codigo: str) -> dict:
        """Verificar compatibilidad del código"""
        resultado = {
            "estado": "ok",
            "incompatibilidades": [],
            "advertencias": [],
            "sugerencias": [],
        }

        # Verificar f-strings (Python 3.6+)
        if 'f"' in codigo or "f'" in codigo:
            resultado["sugerencias"].append("F-strings detectados (requieren Python 3.6+)")

        # Verificar type hints (Python 3.5+)
        if ": " in codigo and "->" in codigo:
            resultado["sugerencias"].append("Type hints detectados (requieren Python 3.5+)")

        # Verificar walrus operator (Python 3.8+)
        if ":=" in codigo:
            resultado["incompatibilidades"].append("Walrus operator (:=) requiere Python 3.8+")
            resultado["estado"] = "warning"

        # Verificar match/case (Python 3.10+)
        if "match " in codigo and "case " in codigo:
            resultado["incompatibilidades"].append("Match/case requiere Python 3.10+")
            resultado["estado"] = "warning"

        # Verificar si hay especificación de versión
        if "python_requires" not in codigo.lower():
            resultado["advertencias"].append("No se especificó versión de Python requerida")

        return resultado


# Instancia global
agente_revisor_compatibilidad = AgenteRevisorCompatibilidad()
