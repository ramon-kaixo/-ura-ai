"""Memory — wrapper principal de la Memoria Histórica (F26).

Coordina MemoryTimeline + Journal + Snapshot.
Punto de entrada único para toda operación de memoria.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger("ura.memory")

import contextlib
from pathlib import Path

from motor.memory.journal import Journal
from motor.memory.snapshot import load_snapshot as _load_snapshot
from motor.memory.snapshot import save_snapshot as _save_snapshot
from motor.memory.timeline import MemoryTimeline

if TYPE_CHECKING:
    from collections.abc import Callable

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
        encryption_key: str = "",
    ) -> None:
        self._timeline = MemoryTimeline()
        self._journal = Journal(encryption_key=encryption_key)
        self._snapshot_path = snapshot_path
        self._auto_recover = auto_recover
        self._entry_count_since_snapshot = 0
        self._encryption_key = encryption_key

        if journal_path:
            self._journal.open(journal_path)

        if auto_recover and (
            (snapshot_path and Path(snapshot_path).exists()) or (journal_path and Path(journal_path).exists())
        ):
            self._recover()

    # ── API pública ──────────────────────────────────

    @property
    def timeline(self) -> MemoryTimeline:
        return self._timeline

    def append(self, entry: MemoryEntry) -> None:
        """Añade un entry a la timeline y al journal (si está abierto)."""
        if self._shutdown:
            msg = "Memory is shutting down"
            raise RuntimeError(msg)
        self._timeline.append(entry)
        if self._journal.path:
            self._journal.append(entry)
        self._entry_count_since_snapshot += 1
        self._notify_subscribers(entry)
        logger.debug("appended entry=%s ts=%.0f source=%s", entry.entry_id, entry.timestamp, entry.source)

    def state_at(self, timestamp: float) -> MemoryEntry | None:
        return self._timeline.state_at(timestamp)

    def snapshot(self, version: str = "") -> str:
        """Fuerza un snapshot del estado actual."""
        path = self._snapshot_path
        if not path:
            path = f"memory_snapshot_{int(__import__('time').time())}.json"
        checksum = _save_snapshot(self._timeline, path, version=version, encryption_key=self._encryption_key)
        if self._journal.path:
            self._journal.rotate(f"{path}.journal.bak")
        self._entry_count_since_snapshot = 0
        logger.info("snapshot saved entries=%d checksum=%s path=%s", self._timeline.size, checksum, path)
        return checksum

    # ── Persistencia ─────────────────────────────────

    def save(self, path: str, version: str = "") -> str:
        """Guarda un snapshot en la ruta indicada."""
        return _save_snapshot(self._timeline, path, version=version)

    @classmethod
    def load(cls, path: str) -> Memory:
        """Carga un snapshot y construye una Memory."""
        from motor.memory.models import FactRef, MemoryEntry, MemoryEventType, MemoryMetadata

        _header, entries_dict = _load_snapshot(path)

        memory = cls(snapshot_path=path, auto_recover=False)
        for _entry_id, entry_data in sorted(entries_dict.items(), key=lambda kv: kv[1].get("timestamp", 0)):
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
            try:  # noqa: SIM105
                memory._timeline.append(entry)
            except KeyError:
                pass  # duplicados tolerados en carga
        return memory

    # ── Health / Readiness / Liveness ──────────────────

    def health(self) -> dict:
        """Health check. Retorna estado del subsistema."""
        return {
            "service": "memory",
            "status": "ok",
            "entries": self._timeline.size,
            "journal": bool(self._journal.path),
            "snapshot": bool(self._snapshot_path),
            "encryption": bool(self._journal._encryption_key),  # noqa: SLF001
        }

    def readiness(self) -> dict:
        """Readiness check. True si puede aceptar lecturas/escrituras."""
        journal_ok = not self._journal.path or Path(self._journal.path).exists()
        return {
            "service": "memory",
            "ready": journal_ok and not self._shutdown,
        }

    def liveness(self) -> dict:
        """Liveness check. True si el hilo principal responde."""
        return {
            "service": "memory",
            "alive": True,
        }

    # ── Graceful shutdown ──────────────────────────────

    @property
    def _shutdown(self) -> bool:
        return getattr(self, "_shutdown_flag", False)

    def shutdown(self, timeout: int = 30) -> None:
        """Graceful shutdown. Cierra journal, espera operaciones en curso."""
        self._shutdown_flag = True
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            # Esperar a que no haya operaciones en curso
            if self._journal.count > 0:
                time.sleep(0.1)
            else:
                break
        self._journal.close()

    # ── Suscripción de eventos ─────────────────────────

    def subscribe(self, callback: Callable[[MemoryEntry], None]) -> None:
        """Registra un callback que se invoca en cada append."""
        if not hasattr(self, "_subscribers"):
            self._subscribers: list[Callable] = []
        self._subscribers.append(callback)

    def _notify_subscribers(self, entry: MemoryEntry) -> None:
        if hasattr(self, "_subscribers"):
            for cb in self._subscribers:
                try:
                    cb(entry)
                except Exception:
                    logger.exception("Error notificando a subscriber de memoria")

    def close(self) -> None:
        self._journal.close()

    # ── Recuperación ─────────────────────────────────

    def _recover(self) -> None:
        """Recupera estado desde snapshot + journal."""
        from motor.memory.models import FactRef, MemoryEntry, MemoryEventType, MemoryMetadata

        entries_dict: dict = {}
        try:
            _, entries_dict = _load_snapshot(self._snapshot_path)
        except (FileNotFoundError, ValueError):
            entries_dict = {}  # snapshot no disponible, solo journal

        for _entry_id, entry_data in sorted(entries_dict.items(), key=lambda kv: kv[1].get("timestamp", 0)):
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
            with contextlib.suppress(KeyError):
                self._timeline.append(entry)

        # Replay journal entries after snapshot (solo los que no están ya en snapshot)
        journal_entries = self._journal.read_all()
        existing_ids = set(self._timeline.entries.keys())
        for entry_data in journal_entries:
            if entry_data.get("entry_id", "") in existing_ids:
                continue  # ya cargado desde snapshot
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
            with contextlib.suppress(KeyError):
                self._timeline.append(entry)
