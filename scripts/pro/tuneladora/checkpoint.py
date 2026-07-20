"""CheckpointManager — checkpoint + reanudación por fase.

Cada fase registra su estado. Si el pipeline se interrumpe,
la siguiente ejecución reanuda desde la última fase completada.

Checkpoint:
  .nervioso/checkpoint.json
  {
    "pipeline": "mejora",
    "last_completed": "refactor_plugins",
    "phases_done": ["pre", "refactor_plugins"],
    "execution_id": "..."
  }
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class CheckpointManager:
    """Gestiona checkpoints por fase para reanudación tras interrupción."""

    def __init__(self, nervioso: Path, pipeline: str, execution_id: str) -> None:
        self._path = nervioso / "checkpoint.json"
        self._pipeline = pipeline
        self._execution_id = execution_id
        self._phases_done: list[str] = []
        self._phases_skipped: list[str] = []

    def is_done(self, phase: str) -> bool:
        """Una fase está completada si aparece en phases_done."""
        return phase in self._phases_done

    def mark_done(self, phase: str) -> None:
        """Marca una fase como completada."""
        if phase not in self._phases_done:
            self._phases_done.append(phase)
        self._save()

    def mark_skipped(self, phase: str) -> None:
        """Marca una fase como omitida (por checkpoint previo)."""
        if phase not in self._phases_skipped:
            self._phases_skipped.append(phase)
        self._save()

    @property
    def last_completed(self) -> str:
        return self._phases_done[-1] if self._phases_done else ""

    def resume(self) -> bool:
        """Intenta reanudar desde un checkpoint previo.
        Retorna True si se reanudó con éxito.
        """
        if not self._path.exists():
            return False
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if data.get("pipeline") != self._pipeline:
                return False
            if data.get("execution_id") == self._execution_id:
                return False  # misma ejecución, no reanudar
            self._phases_done = data.get("phases_done", [])
            self._phases_skipped = data.get("phases_skipped", [])
            return len(self._phases_done) > 0
        except Exception:
            return False

    def clear(self) -> None:
        """Limpia el checkpoint (ejecución completa o --force)."""
        self._phases_done = []
        self._phases_skipped = []
        if self._path.exists():
            self._path.unlink()

    def _save(self) -> None:
        data = {
            "pipeline": self._pipeline,
            "execution_id": self._execution_id,
            "last_completed": self.last_completed,
            "phases_done": self._phases_done,
            "phases_skipped": self._phases_skipped,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
