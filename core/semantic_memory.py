#!/usr/bin/env python3
"""
URA Semantic Memory - Memoria Semántica con Vector DB
"""

from datetime import UTC, datetime, timedelta
import hashlib
import logging
import requests
from typing import Any

logger = logging.getLogger(__name__)


class MemoryEntry:
    """Entrada de memoria"""

    def __init__(
        self,
        entry_id: str,
        content: str,
        metadata: dict[str, Any] = None,
        importance: float = 0.5,
        ttl_hours: int = None,
    ):
        """
        Inicializar entrada

        Args:
            entry_id: ID
            content: Contenido
            metadata: Metadatos
            importance: Importancia (0-1)
            ttl_hours: Tiempo de vida en horas
        """
        self.entry_id = entry_id
        self.content = content
        self.metadata = metadata or {}
        self.importance = importance
        self.created_at = datetime.now(UTC)
        self.ttl = timedelta(hours=ttl_hours) if ttl_hours else None
        self.access_count = 0
        self.last_accessed: datetime | None = None

    def is_expired(self) -> bool:
        """Verificar si expiró"""
        if not self.ttl:
            return False
        return datetime.now(UTC) > (self.created_at + self.ttl)

    def access(self) -> None:
        """Registrar acceso"""
        self.access_count += 1
        self.last_accessed = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convertir a diccionario"""
        return {
            "entry_id": self.entry_id,
            "content": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "importance": self.importance,
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class SemanticMemory:
    """Memoria Semántica"""

    def __init__(self, memory_id: str, dimension: int = 1536, vector_db=None, search_engine=None):
        """
        Inicializar memoria

        Args:
            memory_id: ID
            dimension: Dimensión de embeddings
            vector_db: Instancia de VectorDatabase (opcional)
            search_engine: Instancia de SemanticSearchEngine (opcional)
        """
        self.memory_id = memory_id
        self.dimension = dimension
        self.entries: dict[str, MemoryEntry] = {}
        self.collection = None
        self.search_index = None
        self.max_entries = 10000
        self.total_memories = 0
        self._vector_db = vector_db
        self._search_engine = search_engine

    def initialize(self) -> None:
        """Inicializar colecciones"""
        if self._vector_db is None:
            from core.vector_database import VectorDatabase

            self._vector_db = VectorDatabase()

        if self._search_engine is None:
            from core.semantic_search import SemanticSearchEngine

            self._search_engine = SemanticSearchEngine()

        self.collection = self._vector_db.create_collection(
            f"memory_{self.memory_id}", f"Semantic Memory {self.memory_id}", self.dimension
        )

        # Configurar índice de búsqueda
        self.search_index = self._search_engine.create_index(
            f"search_{self.memory_id}", f"Search Index {self.memory_id}", self._simple_embed
        )

        logger.info(f"Semantic memory initialized: {self.memory_id}")

    def _simple_embed(self, text: str) -> list[float]:
        """Función de embedding usando Ollama mxbai-embed-large con fallback a SHA256"""
        try:
            # Intentar usar Ollama para embeddings reales
            response = requests.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "mxbai-embed-large", "prompt": text},
                timeout=5,
            )
            response.raise_for_status()
            embedding = response.json().get("embedding", [])

            if embedding and len(embedding) > 0:
                logger.info(f"Embedding generado con Ollama: {len(embedding)} dimensiones")
                # Ajustar a la dimensión requerida
                if len(embedding) >= self.dimension:
                    return embedding[: self.dimension]
                else:
                    # Si el embedding es más pequeño, rellenar con ceros
                    return embedding + [0.0] * (self.dimension - len(embedding))
        except Exception as e:
            logger.warning(f"Ollama embeddings falló, usando SHA256 fallback: {e}")

        # Fallback a SHA256 (método original)
        # Crear un hash consistente del texto
        hash_obj = hashlib.sha256(text.encode("utf-8"))
        hash_bytes = hash_obj.digest()

        # Generar vector numérico
        vector = []
        for i in range(self.dimension):
            idx = i % len(hash_bytes)
            val = hash_bytes[idx] / 255.0  # Normalizar a [0,1]
            vector.append(val)

        # Normalizar para que la magnitud sea ~1
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        logger.info(f"Embedding generado con SHA256 fallback: {len(vector)} dimensiones")
        return vector

    def add_memory(
        self,
        content: str,
        metadata: dict[str, Any] = None,
        importance: float = 0.5,
        ttl_hours: int = None,
    ) -> str:
        """
        Añadir memoria

        Args:
            content: Contenido
            metadata: Metadatos
            importance: Importancia
            ttl_hours: Tiempo de vida

        Returns:
            ID de la entrada
        """
        entry_id = f"mem_{datetime.now(UTC).timestamp()}"
        entry = MemoryEntry(entry_id, content, metadata, importance, ttl_hours)

        self.entries[entry_id] = entry
        self.total_memories += 1

        # Añadir a vector DB
        embedding = self._simple_embed(content)
        logger.info(f"Embedding generado: {len(embedding) if embedding else 'None'}")
        from core.vector_database import VectorDocument

        doc = VectorDocument(
            entry_id, embedding, {"content": content, "importance": importance, **(metadata or {})}
        )
        self.collection.add_document(doc)

        # Añadir a índice de búsqueda
        from core.semantic_search import SearchDocument

        search_doc = SearchDocument(
            entry_id, content, embedding, {"importance": importance, **(metadata or {})}
        )
        self.search_index.index_document(search_doc)

        logger.info(f"Memory added: {entry_id}")
        return entry_id

    def recall(
        self, query: str, top_k: int = 5, min_importance: float = 0.0
    ) -> list[dict[str, Any]]:
        """
        Recuperar memorias relevantes

        Args:
            query: Consulta
            top_k: Número de resultados
            min_importance: Importancia mínima

        Returns:
            Lista de memorias
        """
        # Limpiar expiradas
        self._cleanup_expired()

        # Búsqueda semántica
        results = self.search_index.search(query, top_k)

        # Filtrar por importancia
        filtered = []
        for r in results:
            entry_id = r.doc.doc_id
            entry = self.entries.get(entry_id)
            if entry and entry.importance >= min_importance:
                entry.access()
                filtered.append(
                    {
                        "entry_id": entry_id,
                        "content": entry.content,
                        "score": r.score,
                        "importance": entry.importance,
                        "metadata": entry.metadata,
                    }
                )

        logger.info(f"Recall: {len(filtered)} memories for query")
        return filtered

    def _cleanup_expired(self) -> int:
        """Limpiar memorias expiradas"""
        expired_ids = []
        for entry_id, entry in self.entries.items():
            if entry.is_expired():
                expired_ids.append(entry_id)

        for entry_id in expired_ids:
            del self.entries[entry_id]
            self.collection.remove_document(entry_id)

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired memories")

        return len(expired_ids)

    def get_memory(self, entry_id: str) -> MemoryEntry | None:
        """
        Obtener memoria

        Args:
            entry_id: ID

        Returns:
            Entrada o None
        """
        entry = self.entries.get(entry_id)
        if entry and not entry.is_expired():
            entry.access()
            return entry
        return None

    def update_importance(self, entry_id: str, new_importance: float) -> bool:
        """
        Actualizar importancia

        Args:
            entry_id: ID
            new_importance: Nueva importancia

        Returns:
            True si actualizada
        """
        entry = self.entries.get(entry_id)
        if entry:
            entry.importance = max(0.0, min(1.0, new_importance))
            logger.info(f"Importance updated: {entry_id} -> {new_importance}")
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "memory_id": self.memory_id,
            "total_entries": len(self.entries),
            "total_memories": self.total_memories,
            "dimension": self.dimension,
            "collection_stats": self.collection.get_stats() if self.collection else {},
            "search_index_stats": self.search_index.get_stats() if self.search_index else {},
        }


class SemanticMemoryManager:
    """Gestor de memoria semántica"""

    def __init__(self):
        """Inicializar gestor"""
        self.memories: dict[str, SemanticMemory] = {}
        self.default_memory: SemanticMemory | None = None

    def create_memory(self, memory_id: str, dimension: int = 1536) -> SemanticMemory:
        """
        Crear memoria

        Args:
            memory_id: ID
            dimension: Dimensión

        Returns:
            Memoria creada
        """
        memory = SemanticMemory(memory_id, dimension)
        memory.initialize()
        self.memories[memory_id] = memory

        if not self.default_memory:
            self.default_memory = memory

        logger.info(f"Semantic memory created: {memory_id}")
        return memory

    def get_memory(self, memory_id: str = None) -> SemanticMemory | None:
        """
        Obtener memoria

        Args:
            memory_id: ID (opcional, usa default)
        """
        if not memory_id:
            return self.default_memory
        return self.memories.get(memory_id)

    def set_default(self, memory_id: str) -> bool:
        """
        Establecer memoria por defecto

        Args:
            memory_id: ID

        Returns:
            True si establecida
        """
        if memory_id in self.memories:
            self.default_memory = self.memories[memory_id]
            return True
        return False

    def add_to_default(
        self, content: str, metadata: dict[str, Any] = None, importance: float = 0.5
    ) -> str | None:
        """
        Añadir a memoria por defecto

        Args:
            content: Contenido
            metadata: Metadatos
            importance: Importancia

        Returns:
            ID de la entrada
        """
        if self.default_memory:
            return self.default_memory.add_memory(content, metadata, importance)
        return None

    def recall_from_default(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Recuperar de memoria por defecto

        Args:
            query: Consulta
            top_k: Número de resultados

        Returns:
            Lista de memorias
        """
        if self.default_memory:
            return self.default_memory.recall(query, top_k)
        return []

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Obtener estadísticas"""
        return {memory_id: memory.get_stats() for memory_id, memory in self.memories.items()}


if __name__ == "__main__":
    manager = SemanticMemoryManager()

    # Create memory
    memory = manager.create_memory("agent_memory", dimension=128)

    # Add memories
    memory.add_memory("URA es un sistema de IA autónomo", {"type": "identity"}, importance=0.9)
    memory.add_memory(
        "El usuario prefiere respuestas concisas", {"type": "preference"}, importance=0.7
    )
    memory.add_memory("Problema resuelto: error de conexión", {"type": "learning"}, importance=0.5)

    # Recall
    results = memory.recall("¿quién es URA?", top_k=2)
    for r in results:
        print(f"- {r['content']} (score: {r['score']:.2f})")

    # Stats
    print(f"Stats: {memory.get_stats()}")
