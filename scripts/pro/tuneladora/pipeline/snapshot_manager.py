from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class SnapshotManager:
    def __init__(self, tuneladora_dir: Path, log_fn: Callable[..., Any] | None = None) -> None:
        self._snapshots_dir = tuneladora_dir / "snapshots"
        self.ok = True
        try:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logging.getLogger("tuneladora.snapshot").error("Cannot create snapshots dir: %s", exc)
            self.ok = False
        self._log = log_fn or (lambda msg: None)

    def take(self, label: str, files: list[Path], head: str = "", model: str = "") -> Path | None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        snapshot_dir = self._snapshots_dir / f"{ts}_{label}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        copied: list[str] = []
        created: list[str] = []
        for f in files:
            if f.exists():
                dest = snapshot_dir / f.relative_to(f.anchor) if f.is_absolute() else snapshot_dir / f
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(f), str(dest))
                copied.append(str(f))
            else:
                created.append(str(f))

        meta = {
            "label": label,
            "created": ts,
            "head": head,
            "model": model,
            "files": copied,
            "created_files": created,
            "count": len(copied),
        }
        (snapshot_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        self._log(f"Snapshot {label}: {len(copied)} restored + {len(created)} new → {snapshot_dir}")
        return snapshot_dir

    def restore(self, snapshot_dir: Path) -> bool:
        meta_file = snapshot_dir / "meta.json"
        if not meta_file.exists():
            self._log(f"No meta.json in {snapshot_dir}")
            return False
        meta = json.loads(meta_file.read_text())
        restored = 0
        for f in meta.get("files", []):
            original = Path(f)
            src = (
                snapshot_dir / original.relative_to(original.anchor)
                if original.is_absolute()
                else snapshot_dir / original
            )
            if src.exists():
                dest = Path(f)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
                restored += 1
        deleted = 0
        for f in meta.get("created_files", []):
            target = Path(f)
            if target.exists():
                target.unlink()
                deleted += 1
        self._log(
            f"Restored {restored}/{meta.get('count', 0)} files, deleted {deleted} created files from {snapshot_dir.name}"
        )
        return True

    def latest(self) -> Path | None:
        snapshots = sorted(self._snapshots_dir.iterdir()) if self._snapshots_dir.exists() else []
        return snapshots[-1] if snapshots else None

    def prune(self, keep: int = 30) -> int:
        snapshots = sorted(self._snapshots_dir.iterdir()) if self._snapshots_dir.exists() else []
        removed = 0
        for s in snapshots[:-keep]:
            shutil.rmtree(str(s), ignore_errors=True)
            removed += 1
        if removed:
            self._log(f"Pruned {removed} old snapshots (keeping {keep})")
        return removed
