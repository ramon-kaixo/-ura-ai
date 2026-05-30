#!/usr/bin/env python3
"""
Agente Revisor de Código - URA App
Revisa código generado
"""

import ast
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgenteRevisorCodigo:
    """Revisa código generado"""

    def __init__(self):
        self.nombre = "agente_revisor_codigo"

    def revisar(self, codigo: str, archivo: str = "archivo.py") -> dict:
        """Revisar código Python"""
        resultado = {"estado": "ok", "errores": [], "advertencias": [], "sugerencias": []}

        try:
            # Verificar sintaxis
            ast.parse(codigo)
            resultado["sugerencias"].append("Sintaxis válida")
        except SyntaxError as e:
            resultado["estado"] = "error"
            resultado["errores"].append(f"Error de sintaxis: {e}")

        # Verificar docstring
        if '"""' not in codigo and "'''" not in codigo:
            resultado["advertencias"].append("Falta docstring")

        # Verificar main
        if 'if __name__ == "__main__":' not in codigo:
            resultado["advertencias"].append("Falta bloque if __name__")

        # Verificar imports
        if "import " not in codigo and "from " not in codigo:
            resultado["sugerencias"].append("No hay imports (puede estar bien)")

        return resultado


# Instancia global
agente_revisor_codigo = AgenteRevisorCodigo()
