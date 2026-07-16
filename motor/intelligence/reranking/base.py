"""BaseReranker — interfaz abstracta para módulos de reranking."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseReranker(ABC):
    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]: ...
