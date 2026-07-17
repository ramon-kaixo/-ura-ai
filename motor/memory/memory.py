"""Memory — wrapper principal de la Memoria Histórica (F26).

Coordina MemoryTimeline + Journal + Snapshot.
Punto de entrada único para toda operación de memoria.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from motor.memory.journal import Journal
from motor.memory.snapshot import load_snapshot as _load_snapshot
from motor.memory.snapshot import save_snapshot as _save_snapshot
from motor.memory.timeline import MemoryTimeline

if TYPE_CHECKING:
    from motor.memory.models import MemoryEntry


class Memory:
    """Memoria Histórica del sistema.

    Contiene la MemoryTimeline completa.
    Gestiona persistencia via Journal + Snapshot.
    Es el único punto de entrada para escribir y consultar la memoria.
    """

    def __init__(
        self,
        journal_path: str = "",
        snapshot_path: str = "",
        auto_recover: bool = True,
    ) -> None:
        self._timeline = MemoryTimeline()
        self._journal = Journal()
        self._snapshot_path = snapshot_path
        self._auto_recover = auto_recover
        self._entry_count_since_snapshot = 0

        if journal_path:
            self._journal.open(journal_path)

        if auto_recover and snapshot_path and os.path.exists(snapshot_path):
            self._recover()

    # ── API pública ──────────────────────────────────

    @property
    def timeline(self) -> MemoryTimeline:
        return self._timeline

    def append(self, entry: MemoryEntry) -> None:
        """Añade un entry a la timeline y al journal (si está abierto)."""
        self._timeline.append(entry)
        if self._journal.path:
            self._journal.append(entry)
        self._entry_count_since_snapshot += 1

    def state_at(self, timestamp: float) -> MemoryEntry | None:
        return self._timeline.state_at(timestamp)

    def snapshot(self, version: str = "") -> str:
        """Fuerza un snapshot del estado actual."""
        path = self._snapshot_path
        if not path:
            path = f"memory_snapshot_{int(__import__('time').time())}.json"
        checksum = _save_snapshot(self._timeline, path, version=version)
        self._journal.rotate(f"{path}.journal.bak")
        self._entry_count_since_snapshot = 0
        return checksum

    # ── Persistencia ─────────────────────────────────

    def save(self, path: str, version: str = "") -> str:
        """Guarda un snapshot en la ruta indicada."""
        return _save_snapshot(self._timeline, path, version=version)

    @classmethod
    def load(cls, path: str) -> Memory:
        """Carga un snapshot y construye una Memory."""
        from motor.memory.models import FactRef, MemoryEntry, MemoryEventType, MemoryMetadata

        header, entries_dict = _load_snapshot(path)

        memory = cls(snapshot_path=path, auto_recover=False)
        for entry_id, entry_data in sorted(
            entries_dict.items(), key=lambda kv: kv[1].get("timestamp", 0)
        ):
            fact_refs = tuple(
                FactRef(
                    fact_id=r["fact_id"],
                    version_id=r["version_id"],
                    subject=r["subject"],
                    predicate=r["predicate"],
                    object=r["object"],
                )
                for r in entry_data.get("fact_refs", [])
            )
            meta = entry_data.get("metadata", {})
            entry = MemoryEntry(
                entry_id=entry_data["entry_id"],
                timestamp=entry_data["timestamp"],
                fact_refs=fact_refs,
                source=entry_data.get("source", ""),
                event_type=MemoryEventType(entry_data.get("event_type", "system_event")),
                metadata=MemoryMetadata(
                    pipeline_version=meta.get("pipeline_version", ""),
                    fusion_config_hash=meta.get("fusion_config_hash", ""),
                    fact_count=meta.get("fact_count", 0),
                    confidence_avg=meta.get("confidence_avg", 0.0),
                    created_by=meta.get("created_by", ""),
                ),
                snapshot=entry_data.get("snapshot", False),
            )
            try:
                memory._timeline.append(entry)
            except KeyError:
                pass  # duplicados tolerados en carga
        return memory

    def close(self) -> None:
        self._journal.close()

    # ── Recuperación ─────────────────────────────────

    def _recover(self) -> None:
        """Recupera estado desde snapshot + journal."""
        from motor.memory.models import FactRef, MemoryEntry, MemoryEventType, MemoryMetadata

        try:
            _, entries_dict = _load_snapshot(self._snapshot_path)
        except (FileNotFoundError, ValueError):
            return

        for entry_id, entry_data in sorted(
            entries_dict.items(), key=lambda kv: kv[1].get("timestamp", 0)
        ):
            fact_refs = tuple(
                FactRef(
                    fact_id=r["fact_id"],
                    version_id=r["version_id"],
                    subject=r["subject"],
                    predicate=r["predicate"],
                    object=r["object"],
                )
                for r in entry_data.get("fact_refs", [])
            )
            meta = entry_data.get("metadata", {})
            entry = MemoryEntry(
                entry_id=entry_data["entry_id"],
                timestamp=entry_data["timestamp"],
                fact_refs=fact_refs,
                source=entry_data.get("source", ""),
                event_type=MemoryEventType(entry_data.get("event_type", "system_event")),
                metadata=MemoryMetadata(
                    pipeline_version=meta.get("pipeline_version", ""),
                    fusion_config_hash=meta.get("fusion_config_hash", ""),
                    fact_count=meta.get("fact_count", 0),
                    confidence_avg=meta.get("confidence_avg", 0.0),
                    created_by=meta.get("created_by", ""),
                ),
                snapshot=entry_data.get("snapshot", False),
            )
            try:
                self._timeline.append(entry)
            except KeyError:
                pass

        # Replay journal entries after snapshot
        journal_entries = self._journal.read_all()
        for entry_data in journal_entries:
            fact_refs = tuple(
                FactRef(
                    fact_id=r["fact_id"],
                    version_id=r["version_id"],
                    subject=r["subject"],
                    predicate=r["predicate"],
                    object=r["object"],
                )
                for r in entry_data.get("fact_refs", [])
            )
            meta = entry_data.get("metadata", {})
            entry = MemoryEntry(
                entry_id=entry_data["entry_id"],
                timestamp=entry_data["timestamp"],
                fact_refs=fact_refs,
                source=entry_data.get("source", ""),
                event_type=MemoryEventType(entry_data.get("event_type", "system_event")),
                metadata=MemoryMetadata(
                    pipeline_version=meta.get("pipeline_version", ""),
                    fusion_config_hash=meta.get("fusion_config_hash", ""),
                    fact_count=meta.get("fact_count", 0),
                    confidence_avg=meta.get("confidence_avg", 0.0),
                    created_by=meta.get("created_by", ""),
                ),
                snapshot=entry_data.get("snapshot", False),
            )
            try:
                self._timeline.append(entry)
            except KeyError:
                pass
