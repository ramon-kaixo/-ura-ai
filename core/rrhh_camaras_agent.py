#!/usr/bin/env python3
"""
Agente RRHH y Cámaras - Fase 4
Errores en contratos, tipos de contrato, nóminas, cámaras homologadas, LOPD.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RRHH_CONOCIMIENTO = Path(__file__).parent / "rrhh_conocimiento.json"


class RRHHCamarasAgent:
    """Agente de recursos humanos y cámaras de seguridad."""

    def __init__(self):
        self.knowledge = self._load_knowledge(RRHH_CONOCIMIENTO, self._default_knowledge())

    def _load_knowledge(self, path: Path, default: dict) -> dict:
        """Cargar conocimiento RRHH desde JSON."""
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando {path}: {e}")
        return default

    def _default_knowledge(self) -> dict:
        """Conocimiento RRHH por defecto."""
        return {
            "errores_comunes_contratos": [
                "No especificar tipo de contrato",
                "Falta de jornada laboral",
                "No incluir periodo de prueba",
                "Salario inferior al SMI",
                "No registrar en SEPE",
            ],
            "tipos_contrato": {
                "indefinido": "Sin fecha de finalización",
                "fijo_discontinuo": "Para trabajos discontinuos",
                "temporal": "Por obra o servicio determinado",
                "practicas": "Para formación",
            },
            "camaras_homologadas": [
                "Hikvision - Serie EasyIP",
                "Dahua - Serie Pro",
                "Axis - Serie M",
                "Bosch - Serie Flexidome",
            ],
            "normativa_lopd": {
                "videovigilancia": "Requiere cartel informativo",
                "datos": "Registro de fichero en AEPD",
                "conservacion": "Máximo 30 días grabaciones",
            },
        }

    def analizar_contrato(self, tipo: str) -> dict:
        """Analizar tipo de contrato."""
        tipo_lower = tipo.lower()
        contratos = self.knowledge.get("tipos_contrato", {})

        for clave, valor in contratos.items():
            if tipo_lower in clave.lower():
                return {
                    "tipo": clave,
                    "descripcion": valor,
                    "errores_comunes": self.knowledge.get("errores_comunes_contratos", []),
                }

        return {"error": "Tipo de contrato no reconocido"}

    def recomendar_camara(self, tipo_comercio: str, presupuesto: float) -> dict:
        """Recomendar cámara según tipo de comercio y presupuesto."""
        self.knowledge.get("camaras_homologadas", [])

        if presupuesto < 200:
            return {
                "recomendacion": "Dahua - Serie económica",
                "razon": "Ajustado a presupuesto bajo",
                "homologada": True,
            }
        elif presupuesto < 500:
            return {
                "recomendacion": "Hikvision - Serie EasyIP",
                "razon": "Buen balance calidad-precio",
                "homologada": True,
            }
        else:
            return {
                "recomendacion": "Axis - Serie M",
                "razon": "Alta calidad para presupuesto alto",
                "homologada": True,
            }


if __name__ == "__main__":
    agent = RRHHCamarasAgent()
    print("Contrato indefinido:", agent.analizar_contrato("indefinido"))
    print("Cámara bar:", agent.recomendar_camara("bar", 300))
