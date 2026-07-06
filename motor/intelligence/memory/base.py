"""MemoryStore — interfaz abstracta para almacenes de memoria."""

from __future__ import annotations

from abc import ABC, abstractmethod

from motor.intelligence.memory.record import MemoryRecord, MemoryType  # noqa: TC001


class MemoryStore(ABC):
    @abstractmethod
    def store(self, record: MemoryRecord) -> str:
        ...

    @abstractmethod
    def get(self, record_id: str) -> MemoryRecord | None:
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        k: int = 10,
        memory_type: MemoryType | None = None,
    ) -> list[MemoryRecord]:
        ...

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        ...

    @abstractmethod
    def count(self, memory_type: MemoryType | None = None) -> int:
        ...
