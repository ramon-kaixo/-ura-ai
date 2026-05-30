#!/usr/bin/env python3
"""
URA Buscador de Manuales - Agente 4
Descarga manuales de herramientas y los guarda en biblioteca/
"""

from datetime import datetime, UTC
from typing import Any

from core.buscadores.base import BaseSearchAgent, SearchAgentMeta
import logging

logger = logging.getLogger("buscador_manuales")


class BuscadorManuales(BaseSearchAgent):
    META = SearchAgentMeta(
        nombre="manuales",
        categorias=["manuales", "guias", "how-to"],
        keywords_disparadoras=["manual", "guía", "how to", "tutorial", "instalar", "configurar"],
    )

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        try:
            raw = self.descargar_manuales() or []
        except Exception as e:  # noqa: BLE001
            logger.warning("descargar_manuales falló: %s", e)
            return []
        return [
            self.normalize_result(r, fuente_default="manuales")
            for r in raw[:max_results]
            if isinstance(r, dict)
        ]

    def __init__(self, biblioteca_dir: str | None = None):
        """
        Inicializar buscador de manuales

        Args:
            biblioteca_dir: Directorio de biblioteca (opcional)
        """
        if biblioteca_dir is None:
            from pathlib import Path

            biblioteca_dir = str(Path(__file__).parent.parent.parent / "biblioteca" / "manuales")
        self.biblioteca_dir = Path(biblioteca_dir)
        self.herramientas = [
            "black",
            "isort",
            "ruff",
            "mypy",
            "bandit",
            "pylint",
            "pytest",
            "coverage",
        ]
        self.manuales = []
        self.ultima_actualizacion = None

        # Crear directorio si no existe
        self.biblioteca_dir.mkdir(parents=True, exist_ok=True)

    def descargar_manuales(self) -> list[dict[str, Any]]:
        """
        Descargar manuales de herramientas

        Returns:
            Lista de manuales descargados
        """
        logger.info("Descargando manuales de herramientas...")

        manuales_descargados = []

        for herramienta in self.herramientas:
            # Simular descarga (en producción usaría curl/wget)
            manual = self._descargar_manual(herramienta)
            if manual:
                manuales_descargados.append(manual)

        self.ultima_actualizacion = datetime.now(tz=UTC)
        self.manuales.extend(manuales_descargados)

        logger.info(f"Descargados {len(manuales_descargados)} manuales")

        return manuales_descargados

    def _descargar_manual(self, herramienta: str) -> dict[str, Any]:
        """
        Descargar manual de una herramienta

        Args:
            herramienta: Nombre de la herramienta

        Returns:
            Información del manual descargado
        """
        try:
            # Simular descarga de manual (en producción usaría --help, docs, etc.)
            contenido_manual = f"""
Manual de {herramienta}
====================

Descripción: Herramienta de desarrollo Python

Uso:
    {herramienta} [opciones] [archivos]

Opciones principales:
    --help: Muestra ayuda
    --version: Muestra versión
    --verbose: Modo detallado

Ejemplos:
    {herramienta} archivo.py
    {herramienta} --check directorio/
"""

            # Guardar en biblioteca
            archivo_path = self.biblioteca_dir / f"{herramienta}_manual.txt"

            with open(archivo_path, "w") as f:
                f.write(contenido_manual)

            manual_info = {
                "herramienta": herramienta,
                "archivo": str(archivo_path),
                "tamaño": len(contenido_manual),
                "fecha": datetime.now(tz=UTC).isoformat(),
                "url": f"https://pylint.org/{herramienta}",
            }

            logger.info(f"Manual descargado: {herramienta}")

            return manual_info

        except Exception as e:
            logger.error(f"Error descargando manual de {herramienta}: {e}")
            return None

    def get_manual(self, herramienta: str) -> dict[str, Any] | None:
        """
        Obtener manual de una herramienta

        Args:
            herramienta: Nombre de la herramienta

        Returns:
            Información del manual o None
        """
        for manual in self.manuales:
            if manual["herramienta"] == herramienta:
                return manual
        return None

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "total_manuales": len(self.manuales),
            "ultima_actualizacion": (
                self.ultima_actualizacion.isoformat() if self.ultima_actualizacion else None
            ),
            "herramientas": len(self.herramientas),
            "directorio": str(self.biblioteca_dir),
        }


if __name__ == "__main__":
    buscador = BuscadorManuales()

    # Descargar manuales
    manuales = buscador.descargar_manuales()
    print(f"Descargados {len(manuales)} manuales")

    # Obtener manual específico
    manual = buscador.get_manual("black")
    print(f"Manual black: {manual}")

    print(f"Estadísticas: {buscador.get_estadisticas()}")
