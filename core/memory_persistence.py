#!/usr/bin/env python3
"""
Memory Persistence - Sistema de Checkpointing para Memoria Semántica
Guarda automáticamente las memorias añadidas por el ReAct engine en disco.
Al arrancar, carga el historial automáticamente para evitar amnesia.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MemoryPersistence:
    """
    Sistema de persistencia para memoria semántica de URA
    Guarda y carga memorias desde un archivo JSON
    """

    def __init__(self, storage_path: str | None = None):
        """
        Inicializa el sistema de persistencia

        Args:
            storage_path: Ruta del archivo JSON para guardar memorias
        """
        if storage_path is None:
            # Usar ubicación en home para evitar problemas con .gitignore
            home_dir = Path.home()
            storage_path = home_dir / ".ura_memory_store.json"

        self.storage_path = Path(storage_path)
        self._ensure_storage_exists()
        self.memories = self._load_memories()
        logger.info(f"MemoryPersistence inicializado: {len(self.memories)} memorias cargadas")

    def _ensure_storage_exists(self):
        """Asegura que el directorio de almacenamiento existe"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.storage_path.exists():
            # Crear archivo vacío con estructura inicial
            self._save_memories({})
            logger.info(f"Archivo de memoria creado: {self.storage_path}")

    def _load_memories(self) -> dict[str, Any]:
        """Carga memorias desde el archivo JSON"""
        try:
            if self.storage_path.exists() and self.storage_path.stat().st_size > 0:
                with open(self.storage_path, encoding="utf-8") as f:
                    return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Archivo de memoria corrupto, recreando: {self.storage_path}")
        except Exception as e:
            logger.error(f"Error cargando memorias: {e}")

        return {}

    def _save_memories(self, memories: dict[str, Any]):
        """Guarda memorias en el archivo JSON"""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(memories, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando memorias: {e}")

    def add_memory(self, memory_id: str, content: str, metadata: dict[str, Any] | None = None):
        """
        Añade una nueva memoria y la persiste en disco

        Args:
            memory_id: ID único de la memoria
            content: Contenido de la memoria
            metadata: Metadatos opcionales (tipo, importancia, etc.)
        """
        if metadata is None:
            metadata = {}

        timestamp = datetime.now().isoformat()

        memory_entry = {
            "id": memory_id,
            "content": content,
            "timestamp": timestamp,
            "metadata": metadata,
        }

        self.memories[memory_id] = memory_entry
        self._save_memories(self.memories)

        logger.info(f"Memoria guardada: {memory_id} (total: {len(self.memories)})")

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        """
        Recupera una memoria por su ID

        Args:
            memory_id: ID de la memoria a recuperar

        Returns:
            Dict con la memoria o None si no existe
        """
        return self.memories.get(memory_id)

    def get_all_memories(self) -> list[dict[str, Any]]:
        """
        Recupera todas las memorias

        Returns:
            Lista de todas las memorias
        """
        return list(self.memories.values())

    def search_memories(self, query: str) -> list[dict[str, Any]]:
        """
        Busca memorias por contenido

        Args:
            query: Texto a buscar

        Returns:
            Lista de memorias que coinciden con la búsqueda
        """
        query_lower = query.lower()
        results = []

        for memory in self.memories.values():
            if query_lower in memory["content"].lower():
                results.append(memory)

        return results

    def delete_memory(self, memory_id: str) -> bool:
        """
        Elimina una memoria por su ID

        Args:
            memory_id: ID de la memoria a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        if memory_id in self.memories:
            del self.memories[memory_id]
            self._save_memories(self.memories)
            logger.info(f"Memoria eliminada: {memory_id}")
            return True

        return False

    def clear_all(self):
        """Elimina todas las memorias"""
        self.memories = {}
        self._save_memories(self.memories)
        logger.info("Todas las memorias eliminadas")

    def get_stats(self) -> dict[str, Any]:
        """
        Obtiene estadísticas de las memorias

        Returns:
            Dict con estadísticas
        """
        return {
            "total_memories": len(self.memories),
            "storage_path": str(self.storage_path),
            "oldest_memory": self._get_oldest_timestamp(),
            "newest_memory": self._get_newest_timestamp(),
        }

    def _get_oldest_timestamp(self) -> str | None:
        """Obtiene el timestamp de la memoria más antigua"""
        if not self.memories:
            return None

        timestamps = [m["timestamp"] for m in self.memories.values()]
        return min(timestamps)

    def _get_newest_timestamp(self) -> str | None:
        """Obtiene el timestamp de la memoria más reciente"""
        if not self.memories:
            return None

        timestamps = [m["timestamp"] for m in self.memories.values()]
        return max(timestamps)


# Singleton
_memory_persistence = None


def get_memory_persistence(storage_path: str | None = None) -> MemoryPersistence:
    """
    Obtiene la instancia singleton de MemoryPersistence

    Args:
        storage_path: Ruta opcional del archivo de almacenamiento

    Returns:
        Instancia de MemoryPersistence
    """
    global _memory_persistence
    if _memory_persistence is None:
        _memory_persistence = MemoryPersistence(storage_path)
    return _memory_persistence
