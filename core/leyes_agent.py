#!/usr/bin/env python3
"""
Agente de Leyes - Fase 4
Leyes municipales de Pamplona, normativa foral Navarra, leyes estatales.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LEYES_CONOCIMIENTO = Path(__file__).parent / "leyes_conocimiento.json"


class LeyesAgent:
    """Agente de información legal española y foral."""

    def __init__(self):
        self.knowledge = self._load_knowledge(LEYES_CONOCIMIENTO, self._default_knowledge())

    def _load_knowledge(self, path: Path, default: dict) -> dict:
        """Cargar conocimiento legal desde JSON."""
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando {path}: {e}")
        return default

    def _default_knowledge(self) -> dict:
        """Conocimiento legal por defecto."""
        return {
            "leyes_municipales_pamplona": {
                "ordenanza_terraces": "Regulación de terrazas en vía pública",
                "ordenanza_ruido": "Límites de ruido horario",
                "ordenanza_limpieza": "Normas de recogida de residuos",
            },
            "normativa_foral_navarra": {
                "foral_recaudacion": "Competencias recaudatorias forales",
                "impuesto_sucesiones": "Impuesto sobre sucesiones y donaciones",
                "canon_electrico": "Canon sobre producción eléctrica",
            },
            "leyes_estatales": {
                "rgpd": "Reglamento General de Protección de Datos",
                "lop": "Ley Orgánica de Protección de Datos",
                "estatuto_trabajadores": "Estatuto de los Trabajadores",
            },
            "subvenciones": {
                "turismo": "Subvenciones para sector turístico",
                "agricultura": "Ayudas para agricultores",
                "tecnologia": "Subvenciones para digitalización",
            },
        }

    def consultar_normativa(self, tema: str, ambito: str = None) -> dict | None:
        """Consultar normativa por tema y ámbito."""
        tema_lower = tema.lower()

        if ambito:
            ambito_lower = ambito.lower()
            if "municipal" in ambito_lower or "pamplona" in ambito_lower:
                normas = self.knowledge.get("leyes_municipales_pamplona", {})
            elif "foral" in ambito_lower or "navarra" in ambito_lower:
                normas = self.knowledge.get("normativa_foral_navarra", {})
            elif "estatal" in ambito_lower or "españa" in ambito_lower:
                normas = self.knowledge.get("leyes_estatales", {})
            else:
                normas = {}
        else:
            # Buscar en todos los ámbitos
            normas = {}
            normas.update(self.knowledge.get("leyes_municipales_pamplona", {}))
            normas.update(self.knowledge.get("normativa_foral_navarra", {}))
            normas.update(self.knowledge.get("leyes_estatales", {}))

        for clave, valor in normas.items():
            if tema_lower in clave.lower() or tema_lower in valor.lower():
                return {"tema": clave, "descripcion": valor}

        return None

    def buscar_subvencion(self, sector: str) -> list[dict]:
        """Buscar subvención por sector."""
        sector_lower = sector.lower()
        subvenciones = self.knowledge.get("subvenciones", {})
        resultados = []
        for clave, valor in subvenciones.items():
            if sector_lower in clave.lower() or sector_lower in valor.lower():
                resultados.append({"sector": clave, "descripcion": valor})
        return resultados


if __name__ == "__main__":
    agent = LeyesAgent()
    print("Normativa ruido:", agent.consultar_normativa("ruido", "municipal"))
    print("Subvención turismo:", agent.buscar_subvencion("turismo"))
