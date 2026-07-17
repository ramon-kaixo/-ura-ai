"""Memoria Histórica (F26) — modelos de datos.

Contiene MemoryEntry, FactRef, MemoryEventType, MemoryMetadata,
SnapshotHeader. Sin lógica de negocio.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum

# ── IDs deterministas ─────────────────────


def make_entry_id(event_type: str, fact_version_ids: list[str], timestamp: float) -> str:
    """ID determinista de MemoryEntry basado en contenido canónico.

    Participan: event_type + sorted(fact_version_ids) + timestamp.
    NO participan metadatos agregados ni posición en la timeline.
    """
    sorted_ids = sorted(fact_version_ids)
    raw = f"{event_type}:{','.join(sorted_ids)}:{int(timestamp)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── Enums ──────────────────────────────────


class MemoryEventType(StrEnum):
    FACT_ADDED = "fact_added"
    FACT_UPDATED = "fact_updated"
    FACT_REMOVED = "fact_removed"
    ROLLBACK = "rollback"
    SNAPSHOT = "snapshot"
    COMPACTION = "compaction"
    SYSTEM = "system_event"


# ── FactRef ────────────────────────────────


@dataclass(frozen=True)
class FactRef:
    """Referencia inmutable a una versión concreta de un Fact (F25).

    Contiene exactamente fact_id + version_id.
    subject/predicate/object están desnormalizados para consulta.
    history_id se deriva de fact_id.
    """

    fact_id: str
    version_id: str
    subject: str
    predicate: str
    object: str


# ── MemoryMetadata ─────────────────────────


@dataclass(frozen=True)
class MemoryMetadata:
    pipeline_version: str = ""
    fusion_config_hash: str = ""
    fact_count: int = 0
    confidence_avg: float = 0.0
    created_by: str = ""


# ── MemoryEntry ────────────────────────────


@dataclass(frozen=True)
class MemoryEntry:
    """Registro del estado del conocimiento en un instante.

    NO contiene Facts. Solo referencias (FactRef).
    NO es fuente de verdad (esa es FactHistory en F25).
    """

    entry_id: str
    timestamp: float
    fact_refs: tuple[FactRef, ...] = field(default_factory=tuple)
    source: str = ""
    event_type: MemoryEventType = MemoryEventType.SYSTEM
    metadata: MemoryMetadata = field(default_factory=MemoryMetadata)
    snapshot: bool = False


# ── SnapshotHeader ─────────────────────────


SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SnapshotHeader:
    schema_version: int = SNAPSHOT_SCHEMA_VERSION
    snapshot_version: str = ""
    checksum: str = ""
    creation_time: float = 0.0
    compatible_from: str = "0.26.0"
    entry_count: int = 0
    journal_offset: int = 0
