"""Contratos abstractos del módulo Web Intelligence.

Define las interfaces que deben implementar todos los proveedores.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.web.models import Citation, SearchResult, WebDocument


class SearchProvider(ABC):
    """Buscador web. Implementa la búsqueda por query → resultados."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Ejecuta una búsqueda y retorna resultados."""
        ...


class Crawler(ABC):
    """Crawler web. Implementa fetch de URL → HTML."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fetch(self, url: str, timeout: int = 30) -> str:
        """Obtiene el HTML de una URL."""
        ...


class Extractor(ABC):
    """Extractor de contenido. Implementa HTML → documento estructurado."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def extract(self, html: str, url: str) -> WebDocument:
        """Extrae contenido estructurado desde HTML."""
        ...

    @abstractmethod
    def extract_text(self, html: str) -> str:
        """Extrae solo el texto limpio desde HTML."""
        ...


class Ranker(ABC):
    """Ranking de resultados. Ordena por relevancia y calidad."""

    @abstractmethod
    def rank(
        self,
        results: list[SearchResult],
        query: str,
    ) -> list[SearchResult]:
        """Ordena resultados según relevancia."""
        ...


class Summarizer(ABC):
    """Resumidor multi-fuente. Sintetiza documentos en un resumen con citas."""

    @abstractmethod
    def summarize(
        self,
        query: str,
        documents: list[WebDocument],
    ) -> tuple[str, list[Citation]]:
        """Genera resumen con citas a partir de documentos."""
        ...


class SourceValidator(ABC):
    """Validador de fuentes. Evalúa calidad y confianza de una URL o dominio."""

    @abstractmethod
    def validate(self, url: str, document: WebDocument | None = None) -> float:
        """Retorna un score de confianza (0.0 - 1.0) para la fuente."""
        ...

    @abstractmethod
    def is_blocked(self, url: str) -> bool:
        """Verifica si una URL está bloqueada (robots.txt, lista negra)."""
        ...
