#!/usr/bin/env python3
"""
URA Semantic Search - Búsqueda semántica
"""

import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class SearchDocument:
    """Documento de búsqueda"""

    def __init__(
        self,
        doc_id: str,
        content: str,
        embedding: list[float] = None,
        metadata: dict[str, Any] = None,
    ):
        """
        Inicializar documento

        Args:
            doc_id: ID del documento
            content: Contenido textual
            embedding: Vector de embedding
            metadata: Metadatos
        """
        self.doc_id = doc_id
        self.content = content
        self.embedding = embedding
        self.metadata = metadata or {}
        self.indexed_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convertir a diccionario"""
        return {
            "doc_id": self.doc_id,
            "content": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "has_embedding": self.embedding is not None,
            "metadata": self.metadata,
        }


class SearchResult:
    """Resultado de búsqueda"""

    def __init__(self, doc: SearchDocument, score: float):
        """
        Inicializar resultado

        Args:
            doc: Documento
            score: Puntuación
        """
        self.doc = doc
        self.score = score

    def to_dict(self) -> dict[str, Any]:
        """Convertir a diccionario"""
        return {
            "doc_id": self.doc.doc_id,
            "score": self.score,
            "content": self.doc.content,
            "metadata": self.doc.metadata,
        }


class SemanticSearchIndex:
    """Índice de búsqueda semántica"""

    def __init__(self, index_id: str, index_name: str, embed_func: Callable = None):
        """
        Inicializar índice

        Args:
            index_id: ID del índice
            index_name: Nombre del índice
            embed_func: Función de embedding
        """
        self.index_id = index_id
        self.index_name = index_name
        self.embed_func = embed_func
        self.documents: dict[str, SearchDocument] = {}
        self.search_count = 0

    def index_document(self, doc: SearchDocument) -> bool:
        """
        Indexar documento

        Args:
            doc: Documento

        Returns:
            True si indexado
        """
        if doc.embedding is None and self.embed_func:
            doc.embedding = self.embed_func(doc.content)

        if doc.embedding is None:
            logger.warning(f"Document has no embedding: {doc.doc_id}")
            return False

        self.documents[doc.doc_id] = doc
        logger.info(f"Document indexed: {doc.doc_id}")
        return True

    def index_text(self, doc_id: str, content: str, metadata: dict[str, Any] = None) -> bool:
        """
        Indexar texto

        Args:
            doc_id: ID del documento
            content: Contenido
            metadata: Metadatos

        Returns:
            True si indexado
        """
        doc = SearchDocument(doc_id, content, metadata=metadata)
        return self.index_document(doc)

    def remove_document(self, doc_id: str) -> bool:
        """
        Eliminar documento

        Args:
            doc_id: ID del documento

        Returns:
            True si eliminado
        """
        if doc_id in self.documents:
            del self.documents[doc_id]
            logger.info(f"Document removed: {doc_id}")
            return True
        return False

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calcular similitud coseno"""
        dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot / (mag1 * mag2)

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        metadata_filter: dict[str, Any] = None,
    ) -> list[SearchResult]:
        """
        Buscar documentos

        Args:
            query: Texto de consulta
            top_k: Número de resultados
            min_score: Puntuación mínima
            metadata_filter: Filtro de metadatos

        Returns:
            Lista de resultados
        """
        if not self.embed_func:
            logger.error("No embed function available")
            return []

        query_embedding = self.embed_func(query)
        if not query_embedding:
            return []

        return self.search_by_vector(query_embedding, top_k, min_score, metadata_filter)

    def search_by_vector(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_score: float = 0.0,
        metadata_filter: dict[str, Any] = None,
    ) -> list[SearchResult]:
        """
        Buscar por vector

        Args:
            query_vector: Vector de consulta
            top_k: Número de resultados
            min_score: Puntuación mínima
            metadata_filter: Filtro de metadatos

        Returns:
            Lista de resultados
        """
        self.search_count += 1
        results = []

        for doc in self.documents.values():
            if not doc.embedding:
                continue

            if metadata_filter:
                match = True
                for key, value in metadata_filter.items():
                    if doc.metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            score = self._cosine_similarity(query_vector, doc.embedding)
            if score >= min_score:
                results.append(SearchResult(doc, score))

        results.sort(key=lambda r: r.score, reverse=True)
        logger.info(f"Search completed: {len(results)} results")
        return results[:top_k]

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "index_id": self.index_id,
            "index_name": self.index_name,
            "total_documents": len(self.documents),
            "search_count": self.search_count,
        }


class SemanticSearchEngine:
    """Motor de búsqueda semántica"""

    def __init__(self):
        """Inicializar motor"""
        self.indexes: dict[str, SemanticSearchIndex] = {}

    def create_index(
        self, index_id: str, index_name: str, embed_func: Callable = None
    ) -> SemanticSearchIndex:
        """
        Crear índice

        Args:
            index_id: ID
            index_name: Nombre
            embed_func: Función de embedding

        Returns:
            Índice creado
        """
        index = SemanticSearchIndex(index_id, index_name, embed_func)
        self.indexes[index_id] = index
        logger.info(f"Search index created: {index_name}")
        return index

    def get_index(self, index_id: str) -> SemanticSearchIndex | None:
        """
        Obtener índice

        Args:
            index_id: ID
        """
        return self.indexes.get(index_id)

    def search(self, index_id: str, query: str, top_k: int = 5) -> list[SearchResult]:
        """
        Buscar en índice

        Args:
            index_id: ID del índice
            query: Consulta
            top_k: Número de resultados

        Returns:
            Lista de resultados
        """
        index = self.get_index(index_id)
        if index:
            return index.search(query, top_k)
        return []

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Obtener estadísticas de todos los índices"""
        return {index_id: index.get_stats() for index_id, index in self.indexes.items()}


# Singleton
_semantic_search_engine: SemanticSearchEngine | None = None


def get_semantic_search_engine() -> SemanticSearchEngine:
    """Obtener el singleton del motor de búsqueda semántica."""
    global _semantic_search_engine
    if _semantic_search_engine is None:
        _semantic_search_engine = SemanticSearchEngine()
    return _semantic_search_engine


if __name__ == "__main__":
    # Test semantic search
    engine = get_semantic_search_engine()

    # Simple embedding
    def simple_embed(text):
        import hashlib

        h = hashlib.md5(text.lower().encode(), usedforsecurity=False).hexdigest()
        return [int(h[i : i + 2], 16) / 255.0 for i in range(0, 20, 2)]

    # Create index
    index = engine.create_index("docs", "Documents", simple_embed)

    # Index documents
    index.index_text("d1", "Machine learning is awesome", {"category": "tech"})
    index.index_text("d2", "Deep learning uses neural networks", {"category": "tech"})
    index.index_text("d3", "Pizza is delicious", {"category": "food"})

    # Search
    results = index.search("artificial intelligence", top_k=2)
    for r in results:
        print(f"- {r.to_dict()}")

    # Stats
    stats = index.get_stats()
    print(f"Stats: {stats}")
