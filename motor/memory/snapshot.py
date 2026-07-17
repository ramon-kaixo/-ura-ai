"""Snapshot — persistencia completa del estado de MemoryTimeline.

Formato: JSON con SnapshotHeader + todos los MemoryEntry.
Escritura atómica via rename.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.memory.models import MemoryEntry, MemoryTimeline


def save_snapshot(timeline: MemoryTimeline, path: str, version: str = "") -> str:
    """Guarda un snapshot completo del timeline.

    Escritura atómica: escribe a archivo temporal + renombra.
    Retorna el checksum SHA-256 del contenido.
    """
    from motor.memory.models import SNAPSHOT_SCHEMA_VERSION

    entries_dict = {}
    for eid, entry in timeline.entries.items():
        entries_dict[eid] = _entry_to_dict(entry)

    data = {
        "header": {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "snapshot_version": version or "",
            "checksum": "",
            "creation_time": __import__("time").time(),
            "compatible_from": "0.26.0",
            "entry_count": len(entries_dict),
            "journal_offset": 0,
        },
        "entries": entries_dict,
    }

    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    data["header"]["checksum"] = checksum[:16]
    raw_final = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(raw_final)
        f.flush()
        os.fsync(f.fileno())  # fsync antes de renombrar
    os.replace(tmp_path, path)
    # fsync del directorio para garantizar que el rename es persistente
    dir_fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)

    return checksum[:16]


def load_snapshot(path: str) -> tuple[dict, dict[str, dict]]:
    """Carga un snapshot desde archivo.

    Retorna (header, entries_dict).
    Verifica checksum si está presente.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Snapshot not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    header = data.get("header", {})
    entries = data.get("entries", {})

    stored_checksum = header.get("checksum", "")
    if stored_checksum:
        data_copy = dict(data)
        data_copy["header"] = dict(header)
        data_copy["header"]["checksum"] = ""
        raw = json.dumps(data_copy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        computed = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        if computed != stored_checksum:
            raise ValueError(
                f"Snapshot checksum mismatch: stored={stored_checksum}, computed={computed}"
            )

    return header, entries


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
