"""Journal — persistencia append-only de MemoryEntry.

Formato: JSON Lines (una entrada por línea).
Rota con cada snapshot. El journal anterior se compacta en el snapshot.
"""

from __future__ import annotations

import json
import os
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.memory.models import MemoryEntry


class Journal:
    """Journal append-only para MemoryEntry.

    Cada línea es un JSON con un MemoryEntry serializado.
    El archivo crece hasta el próximo snapshot, momento en que se rota.
    """

    def __init__(self, path: str = "") -> None:
        self._path = path
        self._file: object = None
        self._count: int = 0
        self._lock = threading.Lock()

    # ── API ──────────────────────────────────────────

    def open(self, path: str) -> None:
        self._path = path
        self._file = open(path, "a", encoding="utf-8")
        self._count = self._count_lines()

    def append(self, entry: MemoryEntry) -> None:
        if self._file is None:
            raise RuntimeError("Journal not open")
        line = json.dumps(self._entry_to_dict(entry), ensure_ascii=False)
        with self._lock:
            self._file.write(line + "\n")
            self._file.flush()
            self._count += 1

    def read_all(self) -> list[dict]:
        """Lee todas las líneas del journal, omitiendo las corruptas."""
        if not self._path or not os.path.exists(self._path):
            return []
        result: list[dict] = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # línea corrupta: omitir
        return result

    def rotate(self, new_path: str) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
            if self._path and os.path.exists(self._path):
                os.rename(self._path, new_path)
            if self._path:
                self._file = open(self._path, "a", encoding="utf-8")
            self._count = 0

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None

    @property
    def count(self) -> int:
        return self._count

    @property
    def path(self) -> str:
        return self._path

    # ── Helpers ──────────────────────────────────────

    @staticmethod
    def _entry_to_dict(entry: MemoryEntry) -> dict:
        return {
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp,
            "fact_refs": [
                {
                    "fact_id": r.fact_id,
                    "version_id": r.version_id,
                    "subject": r.subject,
                    "predicate": r.predicate,
                    "object": r.object,
                }
                for r in entry.fact_refs
            ],
            "source": entry.source,
            "event_type": entry.event_type.value,
            "metadata": {
                "pipeline_version": entry.metadata.pipeline_version,
                "fusion_config_hash": entry.metadata.fusion_config_hash,
                "fact_count": entry.metadata.fact_count,
                "confidence_avg": entry.metadata.confidence_avg,
                "created_by": entry.metadata.created_by,
            },
            "snapshot": entry.snapshot,
        }

    def _count_lines(self) -> int:
        if not self._path or not os.path.exists(self._path):
            return 0
        with open(self._path, encoding="utf-8") as f:
            return sum(1 for _ in f)
