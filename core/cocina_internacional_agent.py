#!/usr/bin/env python3
"""
Agente de Cocina Internacional - Fase 4
Recetas mexicanas, peruanas, japonesas y otras populares en España.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RECETAS_INTERNACIONALES = Path(__file__).parent / "recetas_internacionales.json"


class CocinaInternacionalAgent:
    """Agente de cocina internacional."""

    def __init__(self):
        self.recetas = self._load_recetas(RECETAS_INTERNACIONALES, self._default_recetas())

    def _load_recetas(self, path: Path, default: list) -> list:
        """Cargar recetas desde JSON."""
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando {path}: {e}")
        return default

    def _default_recetas(self) -> list:
        """Recetas por defecto internacionales."""
        return [
            {
                "nombre": "Tacos al pastor",
                "pais": "México",
                "ingredientes": ["cerdo", "piña", "cilantro"],
                "popular_en_espana": True,
            },
            {
                "nombre": "Ceviche",
                "pais": "Perú",
                "ingredientes": ["pescado", "limón", "cebolla"],
                "popular_en_espana": True,
            },
            {
                "nombre": "Sushi",
                "pais": "Japón",
                "ingredientes": ["arroz", "pescado", "alga"],
                "popular_en_espana": True,
            },
            {
                "nombre": "Curry",
                "pais": "India",
                "ingredientes": ["especias", "pollo", "arroz"],
                "popular_en_espana": True,
            },
            {
                "nombre": "Pasta carbonara",
                "pais": "Italia",
                "ingredientes": ["pasta", "huevo", "bacon"],
                "popular_en_espana": True,
            },
        ]

    def buscar_receta_internacional(self, plato: str, pais: str = None) -> list[dict]:
        """Buscar receta internacional por plato y país."""
        resultados = []
        for receta in self.recetas:
            plato_match = plato.lower() in receta["nombre"].lower()
            pais_match = pais is None or (pais and pais.lower() in receta["pais"].lower())
            if plato_match and pais_match:
                resultados.append(receta)
        return resultados

    def restaurantes_cercanos(self, tipo_comida: str, ciudad: str) -> list[str]:
        """Restaurantes cercanos (simulado)."""
        return [
            f"Restaurante {tipo_comida} en {ciudad} - Centro",
            f"Restaurante {tipo_comida} en {ciudad} - Zona Norte",
            f"Restaurante {tipo_comida} en {ciudad} - Zona Sur",
        ]


if __name__ == "__main__":
    agent = CocinaInternacionalAgent()
    print("Tacos:", agent.buscar_receta_internacional("tacos", "México"))
    print("Restaurantes:", agent.restaurantes_cercanos("sushi", "Madrid"))
