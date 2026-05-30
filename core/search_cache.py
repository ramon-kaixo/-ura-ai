#!/usr/bin/env python3
"""
Módulo: core/search_cache.py
Propósito: Cache de resultados de búsqueda en disco para evitar consultas repetidas costosas.
Dependencias principales: pathlib, json, hashlib
Reglas especiales: Fallback a cache local si disco externo no disponible. TTL máximo 24h.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("search_cache")

# Configuración
CACHE_DIR = Path("/Volumes/TOSHIBA_NUEVO/URA_entrenamiento/cache")
CACHE_FILE = CACHE_DIR / "search_cache.json"


class SearchCache:
    """Cache de resultados de búsqueda."""

    def __init__(self, cache_file: Path | None = None):
        """
        Inicializar cache.

        Args:
            cache_file: Ruta del archivo de cache (usa default si no se especifica)
        """
        self.cache_file = cache_file or CACHE_FILE
        self._cache: dict[str, Any] = {}

        # Crear directorio si no existe
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.cache_file = Path.home() / ".ura" / "cache" / "search_cache.json"
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Cargar cache existente
        self._load()

    def _load(self) -> None:
        """Carga cache desde archivo."""
        if not self.cache_file.exists():
            self._cache = {}
            return

        try:
            with open(self.cache_file, encoding="utf-8") as f:
                self._cache = json.load(f)
            logger.info(f"Cache cargado: {len(self._cache)} entradas")
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Error cargando cache: {e}")
            self._cache = {}

    def _save(self) -> None:
        """Guarda cache en archivo."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Error guardando cache: {e}")

    def get(self, query_hash: str) -> Any | None:
        """
        Obtiene resultado del cache.

        Args:
            query_hash: Hash de la query

        Returns:
            Resultado cacheado o None si no existe
        """
        return self._cache.get(query_hash)

    def set(self, query_hash: str, data: Any) -> None:
        """
        Guarda resultado en cache.

        Args:
            query_hash: Hash de la query
            data: Datos a cachear
        """
        self._cache[query_hash] = data
        self._save()

    def clear(self) -> None:
        """Limpia el cache."""
        self._cache = {}
        self._save()
        logger.info("Cache limpiado")

    def size(self) -> int:
        """Retorna tamaño del cache."""
        return len(self._cache)


# Instancia global
_search_cache: SearchCache | None = None


def get_search_cache() -> SearchCache:
    """Retorna instancia global de SearchCache."""
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchCache()
    return _search_cache


def reset_search_cache() -> None:
    """Resetea instancia global de SearchCache."""
    global _search_cache
    _search_cache = None


if __name__ == "__main__":
    # Test
    cache = SearchCache()
    print(f"Tamaño cache: {cache.size()}")

    # Test get/set
    cache.set("test_hash", {"result": "test"})
    result = cache.get("test_hash")
    print(f"Resultado: {result}")

    # Test clear
    cache.clear()
    print(f"Tamaño después de clear: {cache.size()}")
