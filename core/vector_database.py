#!/usr/bin/env python3
"""
URA Vector Database - Base de datos vectorial
Soporta ChromaDB con fallback a SQLite + cosine similarity
"""

import ast
import logging
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Verificar disponibilidad de ChromaDB
try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
    logger.info("ChromaDB disponible")
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB no disponible, usando fallback SQLite")


class VectorDocument:
    """Documento vectorial"""

    def __init__(self, doc_id: str, vector: list[float], metadata: dict[str, Any] = None):
        """
        Inicializar documento

        Args:
            doc_id: ID del documento
            vector: Vector de embeddings
            metadata: Metadatos
        """
        self.doc_id = doc_id
        self.vector = vector
        self.metadata = metadata or {}
        self.created_at = datetime.now(UTC)

    def add_metadata(self, key: str, value: Any) -> None:
        """
        Añadir metadato

        Args:
            key: Clave
            value: Valor
        """
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Obtener metadato

        Args:
            key: Clave
            default: Valor por defecto
        """
        return self.metadata.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """Convertir a diccionario"""
        return {
            "doc_id": self.doc_id,
            "vector_dim": len(self.vector),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class VectorCollection:
    """Colección vectorial"""

    def __init__(self, collection_id: str, collection_name: str, dimension: int):
        """
        Inicializar colección

        Args:
            collection_id: ID de la colección
            collection_name: Nombre de la colección
            dimension: Dimensión de los vectores
        """
        self.collection_id = collection_id
        self.collection_name = collection_name
        self.dimension = dimension
        self.documents: dict[str, VectorDocument] = {}

    def add_document(self, doc: VectorDocument) -> bool:
        """
        Añadir documento

        Args:
            doc: Documento a añadir

        Returns:
            True si añadido
        """
        if len(doc.vector) != self.dimension:
            logger.warning(
                f"Vector dimension mismatch: expected {self.dimension}, got {len(doc.vector)}"
            )
            return False

        self.documents[doc.doc_id] = doc
        logger.info(f"Document added to collection: {doc.doc_id}")
        return True

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

    def get_document(self, doc_id: str) -> VectorDocument | None:
        """
        Obtener documento

        Args:
            doc_id: ID del documento
        """
        return self.documents.get(doc_id)

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calcular similitud coseno

        Args:
            vec1: Vector 1
            vec2: Vector 2

        Returns:
            Similitud coseno
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """
        Buscar documentos similares

        Args:
            query_vector: Vector de consulta
            top_k: Número de resultados

        Returns:
            Lista de resultados con similitud
        """
        if len(query_vector) != self.dimension:
            logger.warning("Query vector dimension mismatch")
            return []

        results = []

        for doc_id, doc in self.documents.items():
            similarity = self.cosine_similarity(query_vector, doc.vector)
            results.append({"doc_id": doc_id, "similarity": similarity, "metadata": doc.metadata})

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def filter_by_metadata(self, metadata_filter: dict[str, Any]) -> list[VectorDocument]:
        """
        Filtrar por metadatos

        Args:
            metadata_filter: Filtro de metadatos

        Returns:
            Lista de documentos coincidentes
        """
        results = []

        for doc in self.documents.values():
            match = True
            for key, value in metadata_filter.items():
                if doc.get_metadata(key) != value:
                    match = False
                    break
            if match:
                results.append(doc)

        return results

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "collection_id": self.collection_id,
            "collection_name": self.collection_name,
            "dimension": self.dimension,
            "total_documents": len(self.documents),
        }


class VectorDatabase:
    """Base de datos vectorial"""

    def __init__(self):
        """Inicializar base de datos"""
        self.collections: dict[str, VectorCollection] = {}

    def create_collection(
        self, collection_id: str, collection_name: str, dimension: int
    ) -> VectorCollection:
        """
        Crear colección

        Args:
            collection_id: ID
            collection_name: Nombre
            dimension: Dimensión

        Returns:
            Colección creada
        """
        collection = VectorCollection(collection_id, collection_name, dimension)
        self.collections[collection_id] = collection
        logger.info(f"Vector collection created: {collection_name}")
        return collection

    def get_collection(self, collection_id: str) -> VectorCollection | None:
        """
        Obtener colección

        Args:
            collection_id: ID
        """
        return self.collections.get(collection_id)

    def remove_collection(self, collection_id: str) -> bool:
        """
        Eliminar colección

        Args:
            collection_id: ID

        Returns:
            True si eliminada
        """
        if collection_id in self.collections:
            del self.collections[collection_id]
            logger.info(f"Collection removed: {collection_id}")
            return True
        return False

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Obtener estadísticas de todas las colecciones"""
        return {
            collection_id: collection.get_stats()
            for collection_id, collection in self.collections.items()
        }


class VectorStore:
    """Base de datos vectorial persistente con ChromaDB o fallback SQLite"""

    def __init__(self, persist_directory: str | Path = None, use_chroma: bool = True):
        """
        Inicializar VectorStore

        Args:
            persist_directory: Directorio para persistir datos
            use_chroma: Usar ChromaDB si está disponible (default: True)
        """
        self.persist_directory = (
            Path(persist_directory) if persist_directory else Path.home() / ".ura_vector_store"
        )
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.use_chroma = use_chroma and CHROMADB_AVAILABLE
        self._init_backend()

    def _init_backend(self):
        """Inicializar backend (ChromaDB o SQLite)"""
        if self.use_chroma:
            try:
                self.chroma_client = chromadb.PersistentClient(
                    path=str(self.persist_directory), settings=Settings(anonymized_telemetry=False)
                )
                logger.info(f"ChromaDB inicializado en {self.persist_directory}")
            except Exception as e:
                logger.error(f"Error inicializando ChromaDB: {e}, usando fallback SQLite")
                self.use_chroma = False
                self._init_sqlite()
        else:
            self._init_sqlite()

    def _init_sqlite(self):
        """Inicializar fallback SQLite"""
        self.db_path = self.persist_directory / "vectors.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_sqlite_tables()
        logger.info(f"SQLite fallback inicializado en {self.db_path}")

    def _create_sqlite_tables(self):
        """Crear tablas SQLite para vectores"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                vector TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS frames (
                id TEXT PRIMARY KEY,
                frame_path TEXT NOT NULL,
                descripcion TEXT,
                vector TEXT NOT NULL,
                video_id TEXT,
                timestamp REAL,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calcular similitud coseno"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def agregar_documento(
        self, texto: str, metadatos: dict[str, Any], embedding: list[float], doc_id: str = None
    ) -> str:
        """
        Agregar documento a la base de datos

        Args:
            texto: Texto del documento
            metadatos: Metadatos adicionales
            embedding: Vector de embedding
            doc_id: ID opcional (se genera si no se proporciona)

        Returns:
            ID del documento agregado
        """
        if doc_id is None:
            doc_id = f"doc_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')}"

        metadatos["texto"] = texto

        if self.use_chroma:
            collection = self.chroma_client.get_or_create_collection("documents")
            collection.add(
                documents=[texto], metadatas=[metadatos], embeddings=[embedding], ids=[doc_id]
            )
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO documents (id, vector, metadata, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (doc_id, str(embedding), str(metadatos), datetime.now(UTC).isoformat()),
            )
            self.conn.commit()

        logger.info(f"Documento agregado: {doc_id}")
        return doc_id

    def buscar_similares(
        self, embedding: list[float], top_k: int = 5, collection_name: str = "documents"
    ) -> list[dict]:
        """
        Buscar documentos similares

        Args:
            embedding: Vector de consulta
            top_k: Número de resultados
            collection_name: Nombre de la colección (ChromaDB)

        Returns:
            Lista de resultados con similitud
        """
        if self.use_chroma:
            collection = self.chroma_client.get_or_create_collection(collection_name)
            results = collection.query(query_embeddings=[embedding], n_results=top_k)

            return [
                {
                    "id": results["ids"][0][i],
                    "texto": results["documents"][0][i],
                    "metadatos": results["metadatas"][0][i],
                    "similitud": 1.0
                    - results["distances"][0][i],  # Convertir distancia a similitud
                }
                for i in range(len(results["ids"][0]))
            ]
        else:
            # Fallback SQLite: buscar todos y calcular similitud
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, vector, metadata FROM documents")
            rows = cursor.fetchall()

            results = []
            for row in rows:
                doc_id, vector_str, metadata_str = row
                vector = ast.literal_eval(vector_str)
                metadata = ast.literal_eval(metadata_str)

                similarity = self._cosine_similarity(embedding, vector)
                results.append(
                    {
                        "id": doc_id,
                        "texto": metadata.get("texto", ""),
                        "metadatos": metadata,
                        "similitud": similarity,
                    }
                )

            results.sort(key=lambda x: x["similitud"], reverse=True)
            return results[:top_k]

    def agregar_frame(
        self,
        frame_path: str | Path,
        descripcion: str,
        embedding: list[float],
        video_id: str,
        timestamp: float,
    ) -> str:
        """
        Agregar frame a la base de datos

        Args:
            frame_path: Ruta al frame
            descripcion: Descripción del frame
            embedding: Vector de embedding
            video_id: ID del vídeo
            timestamp: Timestamp en segundos

        Returns:
            ID del frame agregado
        """
        frame_id = f"frame_{video_id}_{timestamp:.2f}"

        if self.use_chroma:
            collection = self.chroma_client.get_or_create_collection("frames")
            collection.add(
                documents=[descripcion],
                metadatos=[
                    {"frame_path": str(frame_path), "video_id": video_id, "timestamp": timestamp}
                ],
                embeddings=[embedding],
                ids=[frame_id],
            )
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO frames (id, frame_path, descripcion, vector, video_id, timestamp, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    frame_id,
                    str(frame_path),
                    descripcion,
                    str(embedding),
                    video_id,
                    timestamp,
                    datetime.now(UTC).isoformat(),
                ),
            )
            self.conn.commit()

        logger.info(f"Frame agregado: {frame_id}")
        return frame_id

    def buscar_frames(
        self, embedding: list[float], video_id: str = None, top_k: int = 5
    ) -> list[dict]:
        """
        Buscar frames similares

        Args:
            embedding: Vector de consulta
            video_id: Filtrar por ID de vídeo (opcional)
            top_k: Número de resultados

        Returns:
            Lista de frames con similitud
        """
        if self.use_chroma:
            collection = self.chroma_client.get_or_create_collection("frames")

            if video_id:
                results = collection.query(
                    query_embeddings=[embedding], where={"video_id": video_id}, n_results=top_k
                )
            else:
                results = collection.query(query_embeddings=[embedding], n_results=top_k)

            return [
                {
                    "id": results["ids"][0][i],
                    "descripcion": results["documents"][0][i],
                    "metadatos": results["metadatas"][0][i],
                    "similitud": 1.0 - results["distances"][0][i],
                }
                for i in range(len(results["ids"][0]))
            ]
        else:
            cursor = self.conn.cursor()

            if video_id:
                cursor.execute(
                    "SELECT id, frame_path, descripcion, vector, timestamp FROM frames WHERE video_id = ?",
                    (video_id,),
                )
            else:
                cursor.execute("SELECT id, frame_path, descripcion, vector, timestamp FROM frames")

            rows = cursor.fetchall()

            results = []
            for row in rows:
                frame_id, frame_path, descripcion, vector_str, timestamp = row
                vector = ast.literal_eval(vector_str)

                similarity = self._cosine_similarity(embedding, vector)
                results.append(
                    {
                        "id": frame_id,
                        "frame_path": frame_path,
                        "descripcion": descripcion,
                        "timestamp": timestamp,
                        "similitud": similarity,
                    }
                )

            results.sort(key=lambda x: x["similitud"], reverse=True)
            return results[:top_k]

    def stats(self) -> dict:
        """Obtener estadísticas"""
        if self.use_chroma:
            return {
                "backend": "chromadb",
                "collections": len(self.chroma_client.list_collections()),
            }
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents")
            docs_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM frames")
            frames_count = cursor.fetchone()[0]

            return {"backend": "sqlite", "documents": docs_count, "frames": frames_count}


def get_vector_store(persist_directory: str | Path = None, use_chroma: bool = True) -> VectorStore:
    """Obtener instancia de VectorStore"""
    return VectorStore(persist_directory=persist_directory, use_chroma=use_chroma)


if __name__ == "__main__":
    # Test VectorStore con embeddings de 384 dimensiones (MiniLM)
    print("--- Testing VectorStore (384 dimensions) ---")
    store = get_vector_store(use_chroma=CHROMADB_AVAILABLE)
    print(f"Backend: {store.stats()['backend']}")

    # Agregar documento de prueba con embedding de 384 dimensiones
    embedding_prueba = [0.1] * 384
    doc_id = store.agregar_documento(
        texto="Documento de prueba", metadatos={"categoria": "test"}, embedding=embedding_prueba
    )
    print(f"Documento agregado: {doc_id}")

    # Buscar similares
    resultados = store.buscar_similares(embedding_prueba, top_k=1)
    print(f"Resultados búsqueda: {resultados}")

    print(f"Stats finales: {store.stats()}")
