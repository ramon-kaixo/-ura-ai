#!/usr/bin/env python3
"""
Agente Revisor de Seguridad - URA App
Revisa seguridad del código
"""

import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgenteRevisorSeguridad:
    """Revisa seguridad del código"""

    def __init__(self):
        self.nombre = "agente_revisor_seguridad"
        self.patrones_peligrosos = [
            r"eval\(",
            r"exec\(",
            r"os\.system\(",
            r"subprocess\.call\(shell=True\)",
            r"pickle\.loads\(",
            r"input\(\)",
            r'password\s*=\s*["\']',
            r'api_key\s*=\s*["\']',
            r'token\s*=\s*["\']',
        ]

    def revisar(self, codigo: str) -> dict:
        """Revisar seguridad del código"""
        resultado = {"estado": "ok", "vulnerabilidades": [], "advertencias": [], "sugerencias": []}

        for patron in self.patrones_peligrosos:
            if re.search(patron, codigo):
                resultado["vulnerabilidades"].append(f"Patrón peligroso detectado: {patron}")
                resultado["estado"] = "warning"

        # Verificar si hay encriptación
        if "encrypt" not in codigo.lower() and "hash" not in codigo.lower():
            resultado["advertencias"].append("No se detectó encriptación/hashing")

        # Verificar si hay validación
        if "validate" not in codigo.lower() and "sanitize" not in codigo.lower():
            resultado["sugerencias"].append("Considerar agregar validación de entrada")

        return resultado


# Instancia global
agente_revisor_seguridad = AgenteRevisorSeguridad()
