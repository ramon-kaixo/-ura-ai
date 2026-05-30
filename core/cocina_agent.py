#!/usr/bin/env python3
"""
Agente de Cocina - Fase 4
Recetas de Navarra, País Vasco y España.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RECETAS_NAVARRA = Path(__file__).parent / "recetas_navarra.json"
RECETAS_PAISVASCO = Path(__file__).parent / "recetas_paisvasco.json"
RECETAS_ESPANA = Path(__file__).parent / "recetas_espana.json"


class CocinaAgent:
    """Agente de cocina regional española."""

    def __init__(self):
        self.recetas_navarra = self._load_recetas(RECETAS_NAVARRA, self._default_navarra())
        self.recetas_paisvasco = self._load_recetas(RECETAS_PAISVASCO, self._default_paisvasco())
        self.recetas_espana = self._load_recetas(RECETAS_ESPANA, self._default_espana())

    def _load_recetas(self, path: Path, default: list) -> list:
        """Cargar recetas desde JSON."""
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando {path}: {e}")
        return default

    def _default_navarra(self) -> list:
        """Recetas por defecto de Navarra."""
        return [
            {
                "nombre": "Ajoarriero",
                "ingredientes": ["bacalao", "ajo", "aceite", "pan"],
                "region": "Navarra",
                "dificultad": "media",
            },
            {
                "nombre": "Pochas",
                "ingredientes": ["alubias", "chorizo", "morcilla"],
                "region": "Navarra",
                "dificultad": "facil",
            },
            {
                "nombre": "Menestra",
                "ingredientes": ["verduras", "jamón"],
                "region": "Navarra",
                "dificultad": "media",
            },
        ]

    def _default_paisvasco(self) -> list:
        """Recetas por defecto del País Vasco."""
        return [
            {
                "nombre": "Marmitako",
                "ingredientes": ["bonito", "patata", "pimiento"],
                "region": "País Vasco",
                "dificultad": "media",
            },
            {
                "nombre": "Piperrada",
                "ingredientes": ["pimiento", "tomate", "cebolla"],
                "region": "País Vasco",
                "dificultad": "facil",
            },
            {
                "nombre": "Bacalao al pil-pil",
                "ingredientes": ["bacalao", "ajo", "aceite"],
                "region": "País Vasco",
                "dificultad": "dificil",
            },
        ]

    def _default_espana(self) -> list:
        """Recetas por defecto de España."""
        return [
            {
                "nombre": "Paella",
                "ingredientes": ["arroz", "marisco", "azafrán"],
                "region": "España",
                "dificultad": "media",
            },
            {
                "nombre": "Gazpacho",
                "ingredientes": ["tomate", "pepino", "ajo"],
                "region": "España",
                "dificultad": "facil",
            },
            {
                "nombre": "Tortilla española",
                "ingredientes": ["huevo", "patata", "cebolla"],
                "region": "España",
                "dificultad": "facil",
            },
        ]

    def buscar_receta(self, ingredientes: list[str], region: str = None) -> list[dict]:
        """Buscar receta por ingredientes y región."""
        todas = []
        if region:
            region = region.lower()
            if "navarra" in region:
                todas.extend(self.recetas_navarra)
            elif "pais vasco" in region or "vasco" in region:
                todas.extend(self.recetas_paisvasco)
            else:
                todas.extend(self.recetas_espana)
        else:
            todas = self.recetas_navarra + self.recetas_paisvasco + self.recetas_espana

        # Filtrar por ingredientes
        ingredientes_lower = [i.lower() for i in ingredientes]
        resultados = []
        for receta in todas:
            receta_ingredientes = [i.lower() for i in receta.get("ingredientes", [])]
            if any(ing in " ".join(receta_ingredientes) for ing in ingredientes_lower):
                resultados.append(receta)

        return resultados

    def guia_paso_a_paso(self, receta: str) -> str:
        """Guía paso a paso de una receta."""
        return f"Guía para {receta}: 1. Preparar ingredientes. 2. Seguir instrucciones tradicionales. 3. Servir caliente."

    def tendencias_locales(self, ciudad: str) -> list[str]:
        """Tendencias culinarias locales."""
        return [
            f"Platos de temporada en {ciudad}",
            "Cocina local con productos frescos",
            "Fusión tradicional-moderna",
        ]


if __name__ == "__main__":
    agent = CocinaAgent()
    print("Receta bacalao Navarra:", agent.buscar_receta(["bacalao"], "Navarra"))
    print("Receta País Vasco:", agent.buscar_receta(["bonito"], "País Vasco"))
