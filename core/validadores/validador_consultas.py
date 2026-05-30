#!/usr/bin/env python3
"""
Validador de Consultas Externas - URA
Verifica que URA ha consultado internet antes de responder preguntas externas
"""

from datetime import datetime


class ValidadorConsultas:
    """Valida que URA ha hecho consultas externas"""

    def __init__(self):
        self.nombre = "validador_consultas"
        self.historial_consultas = []

    def validar_consultas_realizadas(self, peticion: str, consultas: list[str]) -> dict:
        """Valida que se hayan realizado consultas relevantes"""
        validacion = {
            "peticion": peticion,
            "consultas_realizadas": len(consultas),
            "consultas": consultas,
            "aprobada": False,
            "timestamp": datetime.now().isoformat(),
        }

        # Verificar que hay consultas
        if len(consultas) > 0:
            validacion["aprobada"] = True

        # Guardar en historial
        self.historial_consultas.append(validacion)

        return validacion

    def requiere_consulta_externa(self, peticion: str) -> bool:
        """Determina si la petición requiere consulta externa"""
        palabras_externas = [
            "buscar",
            "google",
            "internet",
            "web",
            "noticias",
            "precio",
            "clima",
            "actualidad",
        ]
        peticion_lower = peticion.lower()
        return any(p in peticion_lower for p in palabras_externas)


# Instancia global
validador_consultas = ValidadorConsultas()
