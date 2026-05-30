#!/usr/bin/env python3
"""
Validador Técnico - URA
Pasa tareas técnicas al técnico correspondiente y certifica el paso
"""

from datetime import datetime


class ValidadorTecnico:
    """Valida paso a técnico para tareas técnicas"""

    def __init__(self):
        self.nombre = "validador_tecnico"
        self.tecnicos = {
            "carta": "tecnico_documentos",
            "vídeo": "tecnico_multimedia",
            "video": "tecnico_multimedia",
            "correos": "tecnico_email",
            "email": "tecnico_email",
            "documento": "tecnico_documentos",
            "presentación": "tecnico_documentos",
            "fotos": "tecnico_multimedia",
        }
        self.historial_pasos = []

    def validar_paso_tecnico(self, peticion: str) -> dict:
        """Valida que la tarea técnica pase al técnico"""
        tipo_tarea = self._identificar_tipo_tarea(peticion)

        validacion = {
            "peticion": peticion,
            "tipo_tarea": tipo_tarea,
            "paso_tecnico": False,
            "tecnico_asignado": None,
            "timestamp": datetime.now().isoformat(),
        }

        if tipo_tarea in self.tecnicos:
            tecnico = self.tecnicos[tipo_tarea]
            validacion["tecnico_asignado"] = tecnico
            validacion["paso_tecnico"] = True

        # Guardar en historial
        self.historial_pasos.append(validacion)

        return validacion

    def _identificar_tipo_tarea(self, peticion: str) -> str:
        """Identifica tipo de tarea técnica"""
        peticion_lower = peticion.lower()

        for tipo, _tecnico in self.tecnicos.items():
            if tipo in peticion_lower:
                return tipo

        return "desconocido"


# Instancia global
validador_tecnico = ValidadorTecnico()
