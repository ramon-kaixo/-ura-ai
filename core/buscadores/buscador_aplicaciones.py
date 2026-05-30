#!/usr/bin/env python3
"""
URA Buscador de Aplicaciones - Agente 3
Busca nuevas herramientas y programas cada semana
"""

from datetime import datetime, timedelta, UTC
from typing import Any

from core.buscadores.base import BaseSearchAgent, SearchAgentMeta
import logging

logger = logging.getLogger("buscador_aplicaciones")


class BuscadorAplicaciones(BaseSearchAgent):
    META = SearchAgentMeta(
        nombre="aplicaciones",
        categorias=["software", "apps", "herramientas"],
        keywords_disparadoras=["app", "aplicación", "software", "herramienta", "tool"],
    )

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        try:
            raw = self.buscar_aplicaciones() or []
        except Exception as e:  # noqa: BLE001
            logger.warning("buscar_aplicaciones falló: %s", e)
            return []
        return [
            self.normalize_result(r, fuente_default="aplicaciones")
            for r in raw[:max_results]
            if isinstance(r, dict)
        ]

    def __init__(self):
        """Inicializar buscador de aplicaciones"""
        self.categorias = ["IDE", "editores", "herramientas AI", "frameworks", "librerías"]
        self.aplicaciones = []
        self.ultima_actualizacion = None

    def buscar_aplicaciones(self) -> list[dict[str, Any]]:
        """
        Buscar nuevas aplicaciones y herramientas

        Returns:
            Lista de aplicaciones encontradas
        """
        logger.info("Buscando nuevas aplicaciones y herramientas...")

        aplicaciones_encontradas = []

        for categoria in self.categorias:
            # Simular búsqueda (en producción usaría GitHub, PyPI, etc.)
            apps_categoria = self._buscar_categoria(categoria)
            aplicaciones_encontradas.extend(apps_categoria)

        self.ultima_actualizacion = datetime.now(tz=UTC)
        self.aplicaciones.extend(aplicaciones_encontradas)

        logger.info(f"Encontradas {len(aplicaciones_encontradas)} aplicaciones")

        return aplicaciones_encontradas

    def _buscar_categoria(self, categoria: str) -> list[dict[str, Any]]:
        """
        Buscar aplicaciones en una categoría

        Args:
            categoria: Categoría de aplicación

        Returns:
            Lista de aplicaciones
        """
        # Simular búsqueda (en producción usaría GitHub API, PyPI, etc.)
        apps_simuladas = [
            {
                "nombre": f"NewTool {categoria}",
                "categoria": categoria,
                "version": "1.0.0",
                "fecha": datetime.now(tz=UTC).isoformat(),
                "url": f"https://github.com/example/newtool-{categoria}",
                "descripcion": f"Nueva herramienta de {categoria}",
            },
            {
                "nombre": f"App {categoria} Pro",
                "categoria": categoria,
                "version": "2.0.0",
                "fecha": (datetime.now(tz=UTC) - timedelta(days=3)).isoformat(),
                "url": f"https://pypi.org/project/app-{categoria}",
                "descripcion": f"Aplicación profesional de {categoria}",
            },
        ]

        return apps_simuladas

    def get_aplicaciones_recientes(self, dias: int = 30) -> list[dict[str, Any]]:
        """
        Obtener aplicaciones de los últimos días

        Args:
            dias: Número de días

        Returns:
            Lista de aplicaciones recientes
        """
        if not self.aplicaciones:
            return []

        cutoff = datetime.now(tz=UTC) - timedelta(days=dias)

        apps_recientes = [
            a for a in self.aplicaciones if datetime.fromisoformat(a["fecha"]) >= cutoff
        ]

        return apps_recientes

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "total_aplicaciones": len(self.aplicaciones),
            "ultima_actualizacion": (
                self.ultima_actualizacion.isoformat() if self.ultima_actualizacion else None
            ),
            "categorias": len(self.categorias),
        }


if __name__ == "__main__":
    buscador = BuscadorAplicaciones()

    # Buscar aplicaciones
    apps = buscador.buscar_aplicaciones()
    print(f"Encontradas {len(apps)} aplicaciones")

    # Obtener recientes
    recientes = buscador.get_aplicaciones_recientes(30)
    print(f"Aplicaciones recientes (30d): {len(recientes)}")

    print(f"Estadísticas: {buscador.get_estadisticas()}")
