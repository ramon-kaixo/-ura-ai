"""Snapshot — persistencia completa del estado de MemoryTimeline.

Formato: JSON con SnapshotHeader + todos los MemoryEntry.
Escritura atómica via rename.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from motor.memory.crypto import decrypt as _decrypt
from motor.memory.crypto import encrypt as _encrypt

if TYPE_CHECKING:
    from motor.memory.models import MemoryEntry, MemoryTimeline


def save_snapshot(timeline: MemoryTimeline, path: str, version: str = "", encryption_key: str = "") -> str:
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

    data_to_write = _encrypt(raw_final.encode("utf-8"), encryption_key) if encryption_key else raw_final.encode("utf-8")

    fd, tmp_path = tempfile.mkstemp(dir=Path(path).parent or ".", suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(data_to_write)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)  # noqa: PTH105
    # fsync del directorio para garantizar que el rename es persistente
    dir_fd = os.open(Path(path).parent or ".", os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)

    return checksum[:16]


def load_snapshot(path: str, encryption_key: str = "") -> tuple[dict, dict[str, dict]]:
    """Carga un snapshot desde archivo.

    Retorna (header, entries_dict).
    Verifica checksum si está presente.
    Soporta cifrado AES-256-CTR si encryption_key se proporciona.
    """
    if not Path(path).exists():
        msg = f"Snapshot not found: {path}"
        raise FileNotFoundError(msg)

    with open(path, "rb") as f:  # noqa: PTH123
        raw = f.read()

    if encryption_key:
        decrypted = _decrypt(raw, encryption_key)
        data = json.loads(decrypted.decode("utf-8"))
    else:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Intentar descifrar sin clave (snapshot legacy)
            msg = "Snapshot is encrypted or corrupted. Provide encryption_key or use unencrypted snapshot."
            raise ValueError(msg)  # noqa: B904

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
            msg = f"Snapshot checksum mismatch: stored={stored_checksum}, computed={computed}"
            raise ValueError(msg)

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
