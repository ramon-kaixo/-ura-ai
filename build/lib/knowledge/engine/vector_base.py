"""Vector protocols and data types for Phase 6 — Backend Vectorial.

Provides:
  Embedder(Protocol)      — Text embedding service.
  VectorStore(Protocol)   — Vector similarity search storage.
  VectorItem, VectorResult — Data transfer objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class Embedder(Protocol):
    """Convierte textos en vectores. Opcional y degradable."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Convierte textos en vectores. Retorna [] si no disponible."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embedding optimizado para queries de búsqueda.
        Por defecto: llama a embed([text])[0].
        Modelos asimétricos (bge, instructor) sobrescriben con instrucción específica.
        """
        ...

    @property
    def vector_size(self) -> int:
        """Dimensión de los vectores que produce."""
        ...

    @property
    def max_input_tokens(self) -> int:
        """Máximo de tokens que el modelo acepta por texto. 0 = desconocido."""
        ...

    @property
    def available(self) -> bool:
        """True si el servicio de embeddings está operativo. O(1), sin side-effects."""
        ...

    def check_available(self) -> bool:
        """Verifica disponibilidad en tiempo real. HTTP + mutación de estado."""
        ...


class VectorStore(Protocol):
    """Almacén vectorial para búsqueda por similitud. Opcional y degradable."""

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,  # noqa: A002
    ) -> list[VectorResult]:
        """Busca vectores similares. Retorna [] si no disponible.
        filter: dict plano {"campo": "valor"} para v1 (equivalencia exacta,
        sin operadores lógicos). Cada backend traduce a su sintaxis nativa.
        """
        ...

    def list_ids(
        self, limit: int = 100, offset: str | None = None
    ) -> tuple[list[str], str | None]:
        """Enumera asset_ids almacenados, paginados.

        Args:
            limit: Máximo de IDs por página.
            offset: Token de paginación (backend-specific).
                    None = primera página.

        Returns:
            Tuple de (ids, next_offset).
            next_offset es None cuando no hay más páginas.
            Si el backend no soporta enumeración, retorna ([], None).
        """
        ...

    def upsert(self, items: list[VectorItem]) -> int:
        """Indexa items en el almacén. Retorna número de insertados."""
        ...

    def delete(self, asset_ids: list[str]) -> int:
        """Elimina vectores del almacén por asset_id."""
        ...

    def count(self) -> int:
        """Número total de vectores en el almacén. 0 si no disponible."""
        ...

    @property
    def available(self) -> bool:
        """True si el almacén vectorial está operativo. O(1), sin side-effects."""
        ...

    def check_available(self) -> bool:
        """Verifica disponibilidad en tiempo real. HTTP + mutación de estado."""
        ...


@dataclass(frozen=True)
class VectorItem:
    """Item para indexar en un VectorStore.

    Encapsula la tripleta (asset_id, vector, text_preview) en un
    tipo con nombre, eliminando errores de orden.
    """

    asset_id: str
    vector: list[float]
    text_preview: str


@dataclass
class VectorResult:
    """Resultado de una búsqueda vectorial."""

    asset_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
