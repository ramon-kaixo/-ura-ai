#!/usr/bin/env python3
"""
Agente Revisor Universal Móvil - URA App
Revisa cualquier tipo de código
"""

import ast


class AgenteRevisorUniversal:
    """Agente revisor universal"""

    def __init__(self):
        self.nombre = "agente_revisor_universal"
        self.box_actual = None

    def asignar_box(self, box: str):
        """Asignar agente a un box específico"""
        self.box_actual = box

    def revisar_codigo(self, codigo: str, tipo: str = "python") -> dict:
        """Revisar código según tipo"""
        if tipo == "python":
            return self._revisar_python(codigo)
        elif tipo == "javascript":
            return self._revisar_javascript(codigo)
        elif tipo == "sql":
            return self._revisar_sql(codigo)
        else:
            return self._revisar_generico(codigo)

    def _revisar_python(self, codigo: str) -> dict:
        resultado = {"estado": "ok", "errores": [], "advertencias": []}
        try:
            ast.parse(codigo)
        except SyntaxError as e:
            resultado["estado"] = "error"
            resultado["errores"].append(f"Sintaxis: {e}")
        return resultado

    def _revisar_javascript(self, codigo: str) -> dict:
        return {"estado": "ok", "advertencias": ["Revisión básica JS"]}

    def _revisar_sql(self, codigo: str) -> dict:
        return {"estado": "ok", "advertencias": ["Revisión básica SQL"]}

    def _revisar_generico(self, codigo: str) -> dict:
        return {"estado": "ok", "advertencias": ["Revisión genérica"]}


# Instancia global
agente_revisor_universal = AgenteRevisorUniversal()
