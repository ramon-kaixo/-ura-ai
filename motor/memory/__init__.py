"""Memoria Histórica (F26).

Preserva, consulta y gestiona la evolución temporal del
conocimiento fusionado.
"""

from motor.memory.journal import Journal
from motor.memory.memory import Memory
from motor.memory.models import (
    FactRef,
    MemoryEntry,
    MemoryEventType,
    MemoryMetadata,
    SnapshotHeader,
    make_entry_id,
)
from motor.memory.snapshot import load_snapshot, save_snapshot
from motor.memory.timeline import MemoryTimeline

__all__ = [
    "FactRef",
    "Journal",
    "Memory",
    "MemoryEntry",
    "MemoryEventType",
    "MemoryMetadata",
    "MemoryTimeline",
    "SnapshotHeader",
    "load_snapshot",
    "make_entry_id",
    "save_snapshot",
]
