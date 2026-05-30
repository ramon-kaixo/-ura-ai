#!/usr/bin/env python3
"""
Embedding Service - Fase 5
Singleton que carga modelo multilingüe con fallback a difflib.
"""

import difflib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers no disponible, usando fallback difflib")


class EmbeddingService:
    """Servicio de embeddings con fallback."""

    _instance: Optional["EmbeddingService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.model = None

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
                logger.info("Modelo de embeddings cargado: paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as e:
                logger.warning(f"Error cargando modelo: {e}, usando fallback difflib")
                self.model = None
        else:
            logger.info("Usando fallback difflib para similitud")

    def encode(self, texto: str) -> list[float]:
        """Codificar texto a embedding."""
        if self.model:
            return self.model.encode(texto).tolist()
        else:
            # Fallback: hash simple del texto
            return [hash(c) % 1000 for c in texto[:384]]

    def batch_encode(self, textos: list[str]) -> list[list[float]]:
        """Codificar lote de textos."""
        if self.model:
            return self.model.encode(textos).tolist()
        else:
            return [self.encode(t) for t in textos]

    def similarity(self, t1: str, t2: str) -> float:
        """Calcular similitud entre dos textos."""
        if self.model:
            emb1 = self.model.encode(t1)
            emb2 = self.model.encode(t2)
            # Cosine similarity
            import numpy as np

            return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
        else:
            # Fallback: difflib SequenceMatcher
            return difflib.SequenceMatcher(None, t1, t2).ratio()


def get_embedding_service() -> EmbeddingService:
    """Obtener instancia singleton del servicio de embeddings."""
    return EmbeddingService()


if __name__ == "__main__":
    es = EmbeddingService()
    vec = es.encode("seguridad")
    print(f"Embedding: {len(vec)} dimensiones")
    sim = es.similarity("hola mundo", "hola mundo")
    print(f"Similitud: {sim}")
    print("OK")
