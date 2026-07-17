"""MemoryTimeline — secuencia ordenada de MemoryEntry.

Append-only. state_at() O(log n). Sin acoplamiento a implementación
concreta de estructura ordenada.
"""

from __future__ import annotations

import bisect
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.memory.models import MemoryEntry


class MemoryTimeline:
    """Secuencia ordenada de MemoryEntry.

    Responsabilidad única: mantener la línea temporal del conocimiento.
    No almacena Facts. No es fuente de verdad.

    Concurrencia:
    - append: single writer (lock exclusivo)
    - consultas: seguras sin lock (entries inmutables)
    """

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}
        self._timeline: list[tuple[float, str]] = []  # (timestamp, entry_id)
        self._by_entity: dict[str, list[str]] = {}
        self._by_event: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    # ── API pública ──────────────────────────────────

    def append(self, entry: MemoryEntry) -> None:
        """Añade un entry al final de la timeline. O(1) amortizado.

        Requiere lock exclusivo. Thread-safe.
        """
        with self._lock:
            if entry.entry_id in self._entries:
                raise KeyError(f"Entry '{entry.entry_id}' already exists")
            self._entries[entry.entry_id] = entry
            self._timeline.append((entry.timestamp, entry.entry_id))
            self._index_entry(entry)

    def state_at(self, timestamp: float) -> MemoryEntry | None:
        """Retorna el entry vigente en el instante dado.

        Regla de desempate: si múltiples entries comparten timestamp,
        prevalece el de mayor entry_id (orden lexicográfico inverso).

        Complejidad: O(log n).
        """
        idx = bisect.bisect_right(self._timeline, (timestamp, "\uffff")) - 1
        if idx < 0:
            return None
        _, entry_id = self._timeline[idx]
        return self._entries.get(entry_id)

    # ── Consultas ────────────────────────────────────

    def by_entity(self, entity: str) -> list[MemoryEntry]:
        """Retorna entries que contienen referencias a una entidad."""
        entry_ids = self._by_entity.get(entity.lower(), [])
        return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def by_time(self, start: float, end: float) -> list[MemoryEntry]:
        """Retorna entries en un rango temporal. O(log n + m)."""
        left = bisect.bisect_left(self._timeline, (start, ""))
        right = bisect.bisect_right(self._timeline, (end, "\uffff"))
        return [
            self._entries[eid]
            for _, eid in self._timeline[left:right]
            if eid in self._entries
        ]

    def by_event(self, event_type: str) -> list[MemoryEntry]:
        """Retorna entries de un tipo de evento."""
        entry_ids = self._by_event.get(event_type, [])
        return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def get(self, entry_id: str) -> MemoryEntry | None:
        """Retorna un entry por su ID."""
        return self._entries.get(entry_id)

    def diff(self, entry_a_id: str, entry_b_id: str) -> dict:
        """Compara dos entries y retorna las diferencias."""
        a = self._entries.get(entry_a_id)
        b = self._entries.get(entry_b_id)
        if a is None or b is None:
            raise KeyError("Entry not found")
        refs_a = {r.fact_id for r in a.fact_refs}
        refs_b = {r.fact_id for r in b.fact_refs}
        return {
            "added": list(refs_b - refs_a),
            "removed": list(refs_a - refs_b),
            "common": list(refs_a & refs_b),
        }

    # ── Propiedades ──────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> dict[str, MemoryEntry]:
        return dict(self._entries)

    @property
    def timeline(self) -> list[tuple[float, str]]:
        return list(self._timeline)

    # ── Internos ─────────────────────────────────────

    def _index_entry(self, entry: MemoryEntry) -> None:
        for ref in entry.fact_refs:
            self._by_entity.setdefault(ref.subject.lower(), []).append(entry.entry_id)
        self._by_event.setdefault(entry.event_type.value, []).append(entry.entry_id)
