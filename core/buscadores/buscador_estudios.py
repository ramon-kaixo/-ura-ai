#!/usr/bin/env python3
"""
URA Buscador de Estudios - Agente 2
Busca estudios académicos sobre IA cada día
"""

from datetime import datetime, timedelta, UTC
from typing import Any

from core.buscadores.base import BaseSearchAgent, SearchAgentMeta
import logging

logger = logging.getLogger("buscador_estudios")


class BuscadorEstudios(BaseSearchAgent):
    META = SearchAgentMeta(
        nombre="estudios",
        categorias=["investigacion", "papers", "academico"],
        keywords_disparadoras=[
            "estudio",
            "investigación",
            "paper",
            "arxiv",
            "académico",
            "research",
        ],
    )

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        try:
            raw = self.buscar_estudios() or []
        except Exception as e:  # noqa: BLE001
            logger.warning("buscar_estudios falló: %s", e)
            return []
        return [
            self.normalize_result(r, fuente_default="estudios")
            for r in raw[:max_results]
            if isinstance(r, dict)
        ]

    def __init__(self):
        """Inicializar buscador de estudios"""
        self.fuentes = ["arxiv.org", "scholar.google.com", "paperswithcode.com"]
        self.estudios = []
        self.ultima_actualizacion = None

    def buscar_estudios(self) -> list[dict[str, Any]]:
        """
        Buscar estudios académicos sobre IA

        Returns:
            Lista de estudios encontrados
        """
        logger.info("Buscando estudios académicos sobre IA...")

        estudios_encontrados = []

        for fuente in self.fuentes:
            # Simular búsqueda (en producción usaría API real)
            estudios_fuente = self._buscar_fuente(fuente)
            estudios_encontrados.extend(estudios_fuente)

        self.ultima_actualizacion = datetime.now(tz=UTC)
        self.estudios.extend(estudios_encontrados)

        logger.info(f"Encontrados {len(estudios_encontrados)} estudios")

        return estudios_encontrados

    def _buscar_fuente(self, fuente: str) -> list[dict[str, Any]]:
        """
        Buscar estudios en una fuente

        Args:
            fuente: Fuente académica

        Returns:
            Lista de estudios
        """
        # Simular búsqueda (en producción usaría API real)
        estudios_simulados = [
            {
                "titulo": f"Advances in AI from {fuente}",
                "autores": ["Author A", "Author B"],
                "fuente": fuente,
                "fecha": datetime.now(tz=UTC).isoformat(),
                "url": f"https://{fuente}/paper-1",
                "resumen": "Estudio sobre avances en IA",
            },
            {
                "titulo": f"Machine Learning Applications from {fuente}",
                "autores": ["Author C", "Author D"],
                "fuente": fuente,
                "fecha": (datetime.now(tz=UTC) - timedelta(days=1)).isoformat(),
                "url": f"https://{fuente}/paper-2",
                "resumen": "Aplicaciones de ML",
            },
        ]

        return estudios_simulados

    def get_estudios_recientes(self, dias: int = 7) -> list[dict[str, Any]]:
        """
        Obtener estudios de los últimos días

        Args:
            dias: Número de días

        Returns:
            Lista de estudios recientes
        """
        if not self.estudios:
            return []

        cutoff = datetime.now(tz=UTC) - timedelta(days=dias)

        estudios_recientes = [
            e for e in self.estudios if datetime.fromisoformat(e["fecha"]) >= cutoff
        ]

        return estudios_recientes

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "total_estudios": len(self.estudios),
            "ultima_actualizacion": (
                self.ultima_actualizacion.isoformat() if self.ultima_actualizacion else None
            ),
            "fuentes": len(self.fuentes),
        }


if __name__ == "__main__":
    buscador = BuscadorEstudios()

    # Buscar estudios
    estudios = buscador.buscar_estudios()
    print(f"Encontrados {len(estudios)} estudios")

    # Obtener recientes
    recientes = buscador.get_estudios_recientes(7)
    print(f"Estudios recientes (7d): {len(recientes)}")

    print(f"Estadísticas: {buscador.get_estadisticas()}")
