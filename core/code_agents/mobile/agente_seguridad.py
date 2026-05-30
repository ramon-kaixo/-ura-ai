#!/usr/bin/env python3
"""
Agente Seguridad Móvil - URA App
Verifica seguridad de cualquier código
"""


class AgenteSeguridad:
    """Agente de seguridad"""

    def __init__(self):
        self.nombre = "agente_seguridad"
        self.box_actual = None

    def asignar_box(self, box: str):
        """Asignar agente a un box específico"""
        self.box_actual = box

    def verificar_seguridad(self, codigo: str) -> dict:
        """Verificar seguridad del código"""
        resultado = {"estado": "ok", "vulnerabilidades": []}

        patrones = ["eval(", "exec(", "password=", "api_key="]
        for patron in patrones:
            if patron in codigo:
                resultado["vulnerabilidades"].append(f"Patrón: {patron}")
                resultado["estado"] = "warning"

        return resultado


# Instancia global
agente_seguridad = AgenteSeguridad()
