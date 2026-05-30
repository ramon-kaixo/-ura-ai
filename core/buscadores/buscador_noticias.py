#!/usr/bin/env python3
"""
URA Buscador de Noticias - Agente 1
Busca noticias sobre URA e IA cada hora
"""

from datetime import datetime, timedelta, UTC
from typing import Any

from core.buscadores.base import BaseSearchAgent, SearchAgentMeta
import logging

logger = logging.getLogger("buscador_noticias")


class BuscadorNoticias(BaseSearchAgent):
    """Buscador de Noticias sobre URA e IA"""

    META = SearchAgentMeta(
        nombre="noticias",
        categorias=["noticias", "actualidad", "news"],
        keywords_disparadoras=["noticia", "news", "actualidad", "hoy", "último", "reciente"],
    )

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        # Delega al buscador legacy y normaliza la salida
        try:
            raw = self.buscar_noticias() or []
        except Exception as e:  # noqa: BLE001
            logger.warning("buscar_noticias falló: %s", e)
            return []
        return [
            self.normalize_result(r, fuente_default="noticias")
            for r in raw[:max_results]
            if isinstance(r, dict)
        ]

    def __init__(self):
        """Inicializar buscador de noticias"""
        self.terminos_busqueda = [
            "URA AI",
            "artificial intelligence",
            "machine learning",
            "LLM",
            "Ollama",
            "AI assistants",
        ]
        self.noticias = []
        self.ultima_actualizacion = None

    def buscar_noticias(self) -> list[dict[str, Any]]:
        """
        Buscar noticias sobre URA e IA

        Returns:
            Lista de noticias encontradas
        """
        logger.info("Buscando noticias sobre URA e IA...")

        noticias_encontradas = []

        for termino in self.terminos_busqueda:
            # Simular búsqueda (en producción usaría API real)
            noticias_termino = self._buscar_termino(termino)
            noticias_encontradas.extend(noticias_termino)

        self.ultima_actualizacion = datetime.now(tz=UTC)
        self.noticias.extend(noticias_encontradas)

        logger.info(f"Encontradas {len(noticias_encontradas)} noticias")

        return noticias_encontradas

    def _buscar_termino(self, termino: str) -> list[dict[str, Any]]:
        """
        Buscar noticias para un término

        Args:
            termino: Término de búsqueda

        Returns:
            Lista de noticias
        """
        # Simular búsqueda (en producción usaría Google News API, etc.)
        noticias_simuladas = [
            {
                "titulo": f"Novedades en {termino}",
                "fuente": "TechNews",
                "fecha": datetime.now(tz=UTC).isoformat(),
                "url": f"https://example.com/{termino}",
                "resumen": f"Artículo sobre {termino}",
            },
            {
                "titulo": f"Avances en {termino}",
                "fuente": "AIWeekly",
                "fecha": (datetime.now(tz=UTC) - timedelta(hours=2)).isoformat(),
                "url": f"https://example.com/{termino}-2",
                "resumen": f"Análisis de {termino}",
            },
        ]

        return noticias_simuladas

    def get_noticias_recientes(self, horas: int = 24) -> list[dict[str, Any]]:
        """
        Obtener noticias de las últimas horas

        Args:
            horas: Número de horas

        Returns:
            Lista de noticias recientes
        """
        if not self.noticias:
            return []

        cutoff = datetime.now(tz=UTC) - timedelta(hours=horas)

        noticias_recientes = [
            n for n in self.noticias if datetime.fromisoformat(n["fecha"]) >= cutoff
        ]

        return noticias_recientes

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "total_noticias": len(self.noticias),
            "ultima_actualizacion": (
                self.ultima_actualizacion.isoformat() if self.ultima_actualizacion else None
            ),
            "terminos_monitoreados": len(self.terminos_busqueda),
        }


if __name__ == "__main__":
    buscador = BuscadorNoticias()

    # Buscar noticias
    noticias = buscador.buscar_noticias()
    print(f"Encontradas {len(noticias)} noticias")

    # Obtener recientes
    recientes = buscador.get_noticias_recientes(24)
    print(f"Noticias recientes (24h): {len(recientes)}")

    print(f"Estadísticas: {buscador.get_estadisticas()}")
