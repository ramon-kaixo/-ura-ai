#!/usr/bin/env python3
"""
Validador de Obediencia URA - Sistema de Control
URA no puede dar una contestación sin pasar por validación
"""

from datetime import datetime
from enum import Enum


class TipoPeticion(Enum):
    """Tipo de petición"""

    INTERNA = "interna"  # Solo conocimiento interno
    EXTERNA = "externa"  # Requiere internet
    TECNICA = "tecnica"  # Requiere técnico (carta, vídeo, correos)
    GENERAL = "general"  # Cualquier otra


class ValidadorObediencia:
    """Validador principal que obliga a URA"""

    def __init__(self):
        self.nombre = "validador_obediencia"
        self.historial_validaciones = []

        # Importar sillas externas
        try:
            from core.validadores.sillas_externas import SillasExternas

            self.sillas_externas = SillasExternas()
        except:
            self.sillas_externas = None

        # Importar validador de consultas
        try:
            from core.validadores.validador_consultas import ValidadorConsultas

            self.validador_consultas = ValidadorConsultas()
        except:
            self.validador_consultas = None

        # Importar validador técnico
        try:
            from core.validadores.validador_tecnico import ValidadorTecnico

            self.validador_tecnico = ValidadorTecnico()
        except:
            self.validador_tecnico = None

    def analizar_peticion(self, peticion: str) -> TipoPeticion:
        """Analiza tipo de petición"""
        peticion_lower = peticion.lower()

        # Palabras clave para externa
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
        if any(p in peticion_lower for p in palabras_externas):
            return TipoPeticion.EXTERNA

        # Palabras clave para técnica
        palabras_tecnicas = [
            "carta",
            "vídeo",
            "video",
            "correos",
            "email",
            "documento",
            "presentación",
            "fotos",
        ]
        if any(p in peticion_lower for p in palabras_tecnicas):
            return TipoPeticion.TECNICA

        return TipoPeticion.GENERAL

    def validar_respuesta(
        self, peticion: str, respuesta: str, consultas_externas: list = None
    ) -> dict:
        """Valida respuesta de URA"""
        tipo = self.analizar_peticion(peticion)
        validacion = {
            "peticion": peticion,
            "tipo_peticion": tipo.value,
            "timestamp": datetime.now().isoformat(),
            "validaciones": [],
            "aprobada": False,
        }

        # Validación según tipo
        if tipo == TipoPeticion.EXTERNA:
            # Requiere sillas externas
            if self.sillas_externas:
                resultado_sillas = self.sillas_externas.validar(peticion, respuesta)
                validacion["validaciones"].append(
                    {"tipo": "sillas_externas", "resultado": resultado_sillas}
                )
                if resultado_sillas.get("aprobada"):
                    validacion["aprobada"] = True
            else:
                validacion["validaciones"].append(
                    {
                        "tipo": "sillas_externas",
                        "resultado": {"error": "Sillas externas no disponibles"},
                    }
                )

        elif tipo == TipoPeticion.TECNICA:
            # Requiere paso a técnico
            if self.validador_tecnico:
                resultado_tecnico = self.validador_tecnico.validar_paso_tecnico(peticion)
                validacion["validaciones"].append(
                    {"tipo": "validador_tecnico", "resultado": resultado_tecnico}
                )
                if resultado_tecnico.get("paso_tecnico"):
                    validacion["aprobada"] = True
            else:
                validacion["validaciones"].append(
                    {
                        "tipo": "validador_tecnico",
                        "resultado": {"error": "Validador técnico no disponible"},
                    }
                )

        else:
            # General: verificar que URA ha intentado
            intento = self._verificar_intento(respuesta)
            validacion["validaciones"].append(
                {"tipo": "verificacion_intento", "resultado": {"intento_verificado": intento}}
            )
            if intento:
                validacion["aprobada"] = True

        # Guardar en historial
        self.historial_validaciones.append(validacion)

        return validacion

    def _verificar_intento(self, respuesta: str) -> bool:
        """Verifica que URA ha intentado realmente"""
        respuestas_rechazo = [
            "no puedo",
            "no se puede",
            "imposible",
            "no disponible",
            "no tengo acceso",
            "no estoy programado",
        ]

        return all(
            rechazo.lower() not in respuesta.lower() for rechazo in respuestas_rechazo
        )  # URA intentó

    def bloquear_respuesta(self, razon: str) -> dict:
        """Bloquea respuesta de URA"""
        return {
            "bloqueada": True,
            "razon": razon,
            "timestamp": datetime.now().isoformat(),
            "requiere_validacion": True,
        }


# Instancia global
validador_obediencia = ValidadorObediencia()
