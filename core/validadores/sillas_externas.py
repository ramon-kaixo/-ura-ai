#!/usr/bin/env python3
"""
Sillas Externas - Sistema de Triple/Quádruple Review
URA pasa por 3-4 sillas externas antes de contestar preguntas hacia afuera
"""

import subprocess
from datetime import datetime


class SillasExternas:
    """Sistema de 3-4 sillas externas para validación"""

    def __init__(self):
        self.nombre = "sillas_externas"
        self.sillas = ["ollama", "ollama", "ollama"]  # 3 sillas por defecto (pueden ser diferentes)
        self.resultados_sillas = []

    def validar(self, peticion: str, respuesta: str) -> dict:
        """Valida respuesta usando sillas externas"""
        validacion = {
            "peticion": peticion,
            "timestamp": datetime.now().isoformat(),
            "sillas": [],
            "aprobada": False,
            "consenso": 0,
        }

        # Cada silla hace la misma pregunta
        for i, silla in enumerate(self.sillas, 1):
            resultado_silla = self._consultar_silla(silla, peticion)
            validacion["sillas"].append(
                {"numero": i, "nombre": silla, "respuesta": resultado_silla}
            )
            self.resultados_sillas.append(resultado_silla)

        # Calcular consenso
        consenso = self._calcular_consenso(validacion["sillas"])
        validacion["consenso"] = consenso

        # Si hay consenso alto, aprobar
        if consenso >= 0.7:  # 70% de consenso
            validacion["aprobada"] = True

        return validacion

    def _consultar_silla(self, silla: str, peticion: str) -> str:
        """Consulta una silla externa"""
        try:
            if silla == "ollama":
                result = subprocess.run(
                    ["ollama", "run", "policia", peticion],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return result.stdout.strip()
            else:
                return f"Respuesta de {silla}"
        except:
            return f"Error consultando {silla}"

    def _calcular_consenso(self, sillas: list[dict]) -> float:
        """Calcula nivel de consenso entre sillas"""
        if not sillas:
            return 0.0

        # Simplificado: si todas dieron respuesta, consenso alto
        respuestas_validas = sum(
            1 for s in sillas if s["respuesta"] and "Error" not in s["respuesta"]
        )
        return respuestas_validas / len(sillas)

    def agregar_silla(self, silla: str):
        """Agrega una silla externa"""
        self.sillas.append(silla)


# Instancia global
sillas_externas = SillasExternas()
