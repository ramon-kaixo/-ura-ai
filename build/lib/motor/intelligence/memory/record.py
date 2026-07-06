"""MemoryRecord — contrato único para todos los tipos de memoria."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class MemoryType(Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


@dataclass
class MemoryRecord:
    id: str = ""
    type: MemoryType = MemoryType.WORKING
    timestamp: str = ""
    source: str = ""
    importance: float = 0.5
    confidence: float = 0.5
    embedding: list[float] | None = None
    tags: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    ttl: int | None = 604800
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:16]
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()
        if self.ttl is not None and self.ttl > 0:
            self.metadata.setdefault("created_at", self.timestamp)
            self.metadata.setdefault("access_count", 0)
            self.metadata.setdefault("last_access", self.timestamp)

    @property
    def is_expired(self) -> bool:
        if self.ttl is None or self.ttl <= 0:
            return False
        created = datetime.fromisoformat(self.metadata.get("created_at", self.timestamp))
        age = (datetime.now(UTC) - created).total_seconds()
        return age > self.ttl

    @property
    def age_seconds(self) -> float:
        created = datetime.fromisoformat(self.metadata.get("created_at", self.timestamp))
        return (datetime.now(UTC) - created).total_seconds()
