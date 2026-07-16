"""Snapshot store — persiste y recupera snapshots entre compilaciones.

Los snapshots se almacenan como JSON en .nervioso/ para evitar
dependencia de SQLite (el scanner trabaja antes de que SQLite exista).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from knowledge.engine.models import Snapshot, SourceObject

log = logging.getLogger("ura.knowledge.snapshot")

_NERVIOSO_DIR = Path(__file__).resolve().parent.parent.parent / ".nervioso"
_SNAPSHOT_FILE = _NERVIOSO_DIR / "last_snapshot.json"
_COMMIT_FILE = _NERVIOSO_DIR / "last_commit.txt"


def save_snapshot(snapshot: Snapshot, commit: str = "HEAD") -> None:
    """Persiste el snapshot y el commit a disco."""
    _NERVIOSO_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "taken_at": snapshot.taken_at,
        "sources": [
            {
                "id": s.id,
                "path": s.path,
                "kind": s.kind,
                "content_sha256": s.content_sha256,
                "size": s.size,
            }
            for s in snapshot.sources
        ],
    }
    _SNAPSHOT_FILE.write_text(json.dumps(data, indent=2))
    _COMMIT_FILE.write_text(commit)
    log.debug("Snapshot saved: %d sources commit=%s", len(snapshot.sources), commit[:12])


def load_snapshot() -> Snapshot | None:
    """Carga el último snapshot. Retorna None si no existe."""
    if not _SNAPSHOT_FILE.exists():
        return None
    try:
        data = json.loads(_SNAPSHOT_FILE.read_text())
        sources = tuple(
            SourceObject(
                id=s["id"],
                path=s["path"],
                kind=s.get("kind", "markdown"),
                content_sha256=s["content_sha256"],
                size=s.get("size", 0),
            )
            for s in data.get("sources", [])
        )
        return Snapshot(sources=sources, taken_at=data.get("taken_at", ""))
    except (json.JSONDecodeError, KeyError) as exc:
        log.warning("Error loading snapshot: %s", exc)
        return None


def load_last_commit() -> str | None:
    """Carga el último commit compilado."""
    if not _COMMIT_FILE.exists():
        return None
    return _COMMIT_FILE.read_text().strip()


def clear_snapshot() -> None:
    """Elimina el snapshot (útil en tests)."""
    _SNAPSHOT_FILE.unlink(missing_ok=True)
    _COMMIT_FILE.unlink(missing_ok=True)
